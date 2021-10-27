from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError
from github import Github, GithubObject

from termcolor import colored

import settings
import github_translation as translate
from RedmineToGitHub import RedmineToGitHub

from textile_to_markdown import TextileToMarkdown
from repositories_to_migrate import FNAL_REDMINE_REPOS, GITHUB_ORG, GITHUB_ORG_REPOS

import argparse
import time

_FNAL_REDMINE_URL = "https://cdcvs.fnal.gov/redmine/"

_GH = Github(login_or_token=settings.GITHUB_LOGIN_OR_TOKEN)
_GH_ORG = _GH.get_organization(GITHUB_ORG)
_GH_ORG_MEMBERS = list(map(lambda e: e.login, _GH_ORG.get_members()))

_REDMINE_TO_GITHUB = RedmineToGitHub(_GH, translate.users)
_TEXTILE_TO_MARKDOWN = TextileToMarkdown(GITHUB_ORG)

_ISSUES_WITH_SUBTASKS = {}
_ISSUES_WITH_RELATIONS = {}
_GH_ISSUES = {}

_GREEN_CHECKMARK = colored("\u2714", "green")
_RED_HEAVY_BALLOT_X = colored("\u2718", "red")
_YELLOW_CIRCLE_BULLET = colored("\u25cf", "yellow")


def redmine_issue_url(issue):
    return f"{_FNAL_REDMINE_URL}issues/{issue.id}"


def concat_mds(*mds):
    mds = list(filter(None, mds))
    if len(mds) == 0:
        return ""
    if len(mds) == 1:
        return mds[0]

    result = mds[0]
    for md in mds[1:]:
        result += "\n\n----\n\n"
        result += md
    return result


def gh_login_or_not_set(redmine, user):
    login = _REDMINE_TO_GITHUB.gh_login(user.name)
    if login is not None:
        return login

    redmine_user = None
    try:
        redmine_user = redmine.user.get(user.id)
    except ResourceNotFoundError:
        return GithubObject.NotSet

    email = getattr(redmine_user, "mail", None)
    login = _REDMINE_TO_GITHUB.search_for_login(user.name, email)
    return GithubObject.NotSet if login is None else login


def at_gh_login_or_name(redmine, user):
    login = gh_login_or_not_set(redmine, user)
    if login is GithubObject.NotSet:
        return user.name

    return "@" + login


def issue_comments(redmine, journals, gh_repo):
    result = []
    for journal in journals:
        if not hasattr(journal, "notes"):
            continue
        if not journal.notes:
            continue

        username = at_gh_login_or_name(redmine, journal.user)
        header = f"*Comment by `{username}` on {journal.created_on}*"
        result.append(
            concat_mds(header, _TEXTILE_TO_MARKDOWN.to_md(journal.notes, gh_repo))
        )
    return result


def migrate_issues_from(redmine, parsed_args, redmine_repo, gh_repo):
    redmine_issues = redmine.project.get(redmine_repo).issues
    repo = None if parsed_args.dry_run else _GH_ORG.get_repo(gh_repo)

    # Ensures that we do not process nested repos to themselves.
    trimmed_redmine_issues = [
        issue for issue in redmine_issues if issue.project.name == redmine_repo
    ]
    n_migrated_issues = 0
    n_issues = len(trimmed_redmine_issues)
    width = len(str(n_issues))

    if n_issues == 0:
        print(f"\nNo {redmine_repo} issues to migrate from Redmine to GitHub")
        return

    if repo is None:
        print(
            f"\nWould migrate {n_issues} {redmine_repo} issues from Redmine to GitHub"
        )
    elif parsed_args.get_users:
        print(f"\nGetting users for Redmine issues in {redmine_repo}")
    else:
        print(f"\nMigrating {n_issues} {redmine_repo} issues from Redmine to GitHub")

    for i, issue in enumerate(reversed(trimmed_redmine_issues)):
        author = at_gh_login_or_name(redmine, issue.author)
        comments = issue_comments(redmine, issue.journals, gh_repo)

        status_bar = f"[{i + 1:{width}d}/{n_issues}]"
        status_bar_width = len(status_bar) * " "

        if parsed_args.get_users:
            print(f"  {status_bar} Gathered users for issue #{issue.id}")
            continue

        has_subtasks_or_relations = False

        if len(issue.children) > 0:
            has_subtasks_or_relations = True
            subtasks = []
            for subtask in issue.children:
                subtasks.append(
                    {
                        "subject": subtask.subject,
                        "redmine_url": redmine_issue_url(subtask),
                    }
                )
            _ISSUES_WITH_SUBTASKS[issue.subject] = subtasks

        if len(issue.relations) > 0:
            has_subtasks_or_relations = True
            relations = []
            for relation in issue.relations:
                related_issue = redmine.issue.get(relation.issue_to_id)
                relations.append(
                    {
                        "subject": related_issue.subject,
                        "redmine_url": redmine_issue_url(related_issue),
                    }
                )
            _ISSUES_WITH_RELATIONS[issue.subject] = relations

        gh_issue_body = concat_mds(
            f"*This issue has been migrated from {redmine_issue_url(issue)} (FNAL account required)*\n"
            f"*Originally created by `{author}` on {issue.created_on}*",
            _TEXTILE_TO_MARKDOWN.to_md(issue.description, gh_repo),
        )

        assigned_to = getattr(issue, "assigned_to", GithubObject.NotSet)
        if assigned_to is not GithubObject.NotSet:
            assigned_to = gh_login_or_not_set(redmine, assigned_to)
            if assigned_to not in _GH_ORG_MEMBERS:
                print(
                    f"  {_RED_HEAVY_BALLOT_X} {status_bar} Could not migrate issue #{issue.id}: {issue.subject}"
                )
                print(
                    f"    {status_bar_width}  - Assignee {assigned_to} is not a member of {_GH_ORG.login}."
                )
                continue

        if repo is None:
            if has_subtasks_or_relations:
                print(
                    f"  {_YELLOW_CIRCLE_BULLET} {status_bar} Would partially migrate Redmine issue #{issue.id}: {issue.subject}"
                )
            else:
                print(
                    f"  {_GREEN_CHECKMARK} {status_bar} Would migrate Redmine issue #{issue.id}: {issue.subject}"
                )
            if parsed_args.verbose:
                print(f"\nIssue #{issue.id}: {issue.subject}")
                if assigned_to is not GithubObject.NotSet:
                    print(f"  - Assigned to {assigned_to}")
                print(gh_issue_body)
                for comment in comments:
                    print(comment)

            continue

        # If actually doing the migration
        gh_labels = [issue.tracker.name.lower()]
        if issue.priority.name.lower() in {"high", "urgent", "immediate"}:
            gh_labels.append("high priority")

        time.sleep(2.5)  # Avoid GitHub's rate limits
        gh_issue = repo.create_issue(
            issue.subject,
            body=gh_issue_body,
            labels=gh_labels,
            assignee=assigned_to,
        )
        for comment in comments:
            time.sleep(2.5)  # Avoid GitHub's rate limits
            gh_issue.create_comment(comment)

        _GH_ISSUES[issue.subject] = (issue, gh_issue)
        if has_subtasks_or_relations:
            print(
                f"  {_YELLOW_CIRCLE_BULLET} {status_bar} Partially migrated Redmine issue #{issue.id}: {issue.subject}"
            )
            print(f"    {status_bar_width}  - {gh_issue.html_url}")
            print(
                f"    {status_bar_width}  - Will not close Redmine issue #{issue.id} until issue dependencies are resolved"
            )
        else:
            symbol = _YELLOW_CIRCLE_BULLET
            redmine_message = f"Could not close Redmine issue #{issue.id}"
            if parsed_args.close_redmine_issues:
                # Update Redmine issue with new GitHub issue ID; then close issue (status ID 5).
                redmine.issue.update(
                    issue.id,
                    notes=f"This issue has moved to {gh_issue.html_url}",
                    status_id=5,
                )
                if redmine.issue.get(issue.id).status.id == 5:
                    # Redmine issue was closed
                    symbol = _GREEN_CHECKMARK
                    redmine_message = f"Closed Redmine issue #{issue.id}"
            print(
                f"  {symbol} {status_bar} Migrated issue #{issue.id}: {issue.subject}"
            )
            print(f"    {status_bar_width}  - {gh_issue.html_url}")
            print(f"    {status_bar_width}  - {redmine_message}")

    return n_migrated_issues, n_issues


def dependency_link(dependency):
    # Check organization first
    time.sleep(2.5)  # Avoid GitHub rate limits
    issues = _GH.search_issues(
        f"{dependency['subject']} in:title is:issue is:open org:{GITHUB_ORG}"
    )
    if issues.totalCount == 1:
        return issues[0].html_url

    time.sleep(2.5)  # Avoid GitHub rate limits
    issues = _GH.search_issues(f"{dependency['subject']} in:title is:issue is:open")
    if issues.totalCount == 1:
        return issues[0].html_url

    return dependency["redmine_url"] + " (FNAL account required)"


def update_gh_issue_body(
    close_redmine_issue, status_bar, redmine, redmine_issue, gh_issue, body_addendum
):
    gh_issue.edit(body=concat_mds(gh_issue.body, body_addendum))
    if close_redmine_issues:
        # Update Redmine issue with new GitHub issue ID; then close issue (status ID 5).
        redmine.issue.update(
            redmine_issue.id,
            notes=f"This issue has moved to {gh_issue.html_url}",
            status_id=5,
        )
    status_bar_width = len(status_bar) * " "
    if redmine.issue.get(redmine_issue.id).status.id != 5:
        print(
            f"  {_YELLOW_CIRCLE_BULLET} {status_bar} Could not complete migration for Redmine issue #{redmine_issue.id}"
        )
        print(
            f"    {status_bar_width}  - Updated issue dependencies for {gh_issue.html_url}"
        )
        print(
            f"    {status_bar_width}  - Could not close Redmine issue #{redmine_issue.id}"
        )
        return

    # Redmine issue was closed
    print(
        f"  {_GREEN_CHECKMARK} {status_bar} Completed migration of Redmine issue #{redmine_issue.id}: {redmine_issue.subject}"
    )
    print(
        f"    {status_bar_width}  - Updated issue dependencies for {gh_issue.html_url}"
    )
    print(f"    {status_bar_width}  - Closed Redmine issue #{redmine_issue.id}")


def migrate(parsed_args):
    redmine = Redmine(
        _FNAL_REDMINE_URL,
        username=settings.REDMINE_USERNAME,
        key=settings.REDMINE_API_PUBLIC_KEY,
    )

    for repo, gh_repo in zip(FNAL_REDMINE_REPOS, GITHUB_ORG_REPOS):
        migrate_issues_from(redmine, parsed_args, repo, gh_repo)

    print()

    if parsed_args.get_users:
        print(_REDMINE_TO_GITHUB.table())
        return

    if not _ISSUES_WITH_SUBTASKS and not _ISSUES_WITH_RELATIONS:
        return

    print("Updating issues with subtasks and related issues")

    # Pre-populate dictionary
    issue_dependencies = {}
    for issue in _ISSUES_WITH_SUBTASKS.keys():
        issue_dependencies.setdefault(issue, "")
    for issue in _ISSUES_WITH_RELATIONS.keys():
        issue_dependencies.setdefault(issue, "")

    n_issues_with_subtasks = len(_ISSUES_WITH_SUBTASKS)
    if n_issues_with_subtasks != 0:
        print(f"  Locating subtasks for {n_issues_with_subtasks} issues")
    for key, subtasks in _ISSUES_WITH_SUBTASKS.items():
        subtasks_str = "\n***Subtasks:***"
        for d in subtasks:
            subtasks_str += "\n- " + dependency_link(d)
        issue_dependencies[key] += subtasks_str

    n_issues_with_relations = len(_ISSUES_WITH_RELATIONS)
    if n_issues_with_relations != 0:
        print(f"  Locating related issues for {n_issues_with_relations} issues")
    for key, subtasks in _ISSUES_WITH_RELATIONS.items():
        subtasks_str = "\n***Related issues:***"
        for d in subtasks:
            subtasks_str += "\n- " + dependency_link(d)
        issue_dependencies[key] += subtasks_str

    n_issues_with_dependencies = len(issue_dependencies)
    width = len(str(n_issues_with_dependencies))
    print(f"\n  Updating {n_issues_with_dependencies} issues")

    for i, (key, body_str) in enumerate(issue_dependencies.items()):
        status_bar = f"[{i + 1:{width}d}/{n_issues_with_dependencies}]"
        entry = _GH_ISSUES.get(key)
        if entry is not None:
            redmine_issue, gh_issue = entry
            update_gh_issue_body(
                parsed_args.close_redmine_issues,
                status_bar,
                redmine,
                redmine_issue,
                gh_issue,
                body_str,
            )
            continue

        print(
            f"  {_RED_HEAVY_BALLOT_X} {status_bar} Cannot find GitHub issue with title '{key}'"
        )

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate issues from FNAL Redmine to GitHub."
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show which migrations would occur without contacting GitHub.",
    )
    parser.add_argument(
        "--close-redmine-issues",
        action="store_true",
        help="Close Redmine issues upon migration to GitHub.",
    )
    parser.add_argument(
        "--get-users",
        action="store_true",
        help="Show which users are mentioned in Redmine issues and comments.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show what information would be published to GitHub.",
    )

    args = parser.parse_args()
    migrate(args)

    if args.dry_run:
        print("Succesful dry run of migration.")
    else:
        print("Migration was succesful.")
