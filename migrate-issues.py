from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError
from github import Github, GithubObject

import settings
import github_translation as translate
from RedmineToGitHub import RedmineToGitHub

from textile_to_markdown import to_md
from repositories_to_markdown import FNAL_REDMINE_REPOS, GITHUB_ORG, GITHUB_ORG_REPOS

import argparse

_FNAL_REDMINE_URL = "https://cdcvs.fnal.gov/redmine/"

_KNOWN_EMAIL_ADDRESSES = {
    "Christopher Green": "greenc@fnal.gov",
    "Marc Paterno": "paterno@fnal.gov",
}


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


def gh_login_or_name(redmine, user, redmine2gh):
    login = redmine2gh.gh_login(user.name)
    if login is not None:
        return login

    email = _KNOWN_EMAIL_ADDRESSES.get(user.name)
    if email is not None:
        login = redmine2gh.search_for_login(user.name, email)
        return login if login is not None else user.name

    redmine_user = None
    try:
        redmine_user = redmine.user.get(user.id)
    except ResourceNotFoundError:
        return user.name

    email = getattr(redmine_user, "mail", None)
    login = redmine2gh.search_for_login(user.name, email)
    return login if login is not None else user.name


def migrate_issues_from(redmine, get_users, redmine2gh, gh_org, redmine_repo, gh_repo):
    redmine_issues = redmine.project.get(redmine_repo).issues
    n_issues = len(redmine_issues)
    width = len(str(n_issues))
    repo = gh_org.get_repo(gh_repo) if gh_org is not None else None

    if n_issues == 0:
        print(f"\nNo {redmine_repo} issues to migrate from Redmine to GitHub")
        return

    if repo is None:
        print(
            f"\nWould migrate {n_issues} {redmine_repo} issues from Redmine to GitHub"
        )
    elif get_users:
        print(f"\nGetting users for Redmine issues in {redmine_repo}")
    else:
        print(f"\nMigrating {n_issues} {redmine_repo} issues from Redmine to GitHub")

    for i, issue in enumerate(redmine_issues):
        if issue.project.name != redmine_repo:
            # Ensures that we do not process nested repos to themselves.
            continue

        if i != 1:
            continue

        status_bar = f"[{i + 1:{width}d}/{n_issues}]"
        comments = []
        author = gh_login_or_name(redmine, issue.author, redmine2gh)
        for journal in issue.journals:
            if not hasattr(journal, "notes"):
                continue
            if not journal.notes:
                continue

            username = gh_login_or_name(redmine, journal.user, redmine2gh)
            header = f"*Comment by `{username}` on {journal.created_on}*"
            comments.append(concat_mds(header, to_md(journal.notes)))

        if get_users:
            print(f"  {status_bar} Gathered users for issue #{issue.id}")
            continue

        subtasks_and_relations = ""
        if len(issue.children) > 0:
            subtasks_and_relations = "\n***Subtasks (FNAL account required):***"
            for subtask in issue.children:
                subtasks_and_relations += (
                    f"\n*- [issue.subject]({redmine_issue_url(subtask)})*"
                )

        if len(issue.relations) > 0:
            subtasks_and_relations += f"\n***Related tasks (FNAL account required):***"
            for relation in issue.relations:
                subtasks_and_relations += (
                    f"\n*- [{issue.subject}]({redmine_issue_url(relation)})*"
                )

        gh_issue_body = concat_mds(
            f"*This issue has been migrated from {redmine_issue_url(issue)} (FNAL account required)*\n"
            f"*Originally created by `{author}`*",
            to_md(issue.description),
            subtasks_and_relations,
        )
        assignee = (
            GithubObject.NotSet
        )  # getattr(issue, "assigned_to", GithubObject.NotSet)

        if repo is None:
            print(f"  {status_bar} Issue #{issue.id}: {issue.subject}")
            print(gh_issue_body)
            for comment in comments:
                print(comment)
        else:
            issue = repo.create_issue(
                issue.subject,
                body=gh_issue_body,
                labels=[issue.tracker.name],
                assignee=assignee,
            )
            for comment in comments:
                issue.create_comment(comment)
            print(f"  {status_bar} Created issue #{issue.number}: {issue.title}")


def migrate(dry_run, get_users):
    redmine = Redmine(
        _FNAL_REDMINE_URL,
        username=settings.REDMINE_USERNAME,
        key=settings.REDMINE_API_PUBLIC_KEY,
    )

    gh = Github(login_or_token=settings.GITHUB_LOGIN_OR_TOKEN)
    gh_org = None
    if not dry_run:
        gh_org = gh.get_organization(GITHUB_ORG)

    redmine2gh = RedmineToGitHub(gh, translate.users)
    for repo, gh_repo in zip(FNAL_REDMINE_REPOS, GITHUB_ORG_REPOS):
        migrate_issues_from(redmine, get_users, redmine2gh, gh_org, repo, gh_repo)

    print()

    if get_users:
        print(redmine2gh.table())


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
        "--get-users",
        action="store_true",
        help="Show which users are mentioned in Redmine issues and comments.",
    )

    args = parser.parse_args()
    migrate(args.dry_run, args.get_users)
