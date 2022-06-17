#!/bin/env python3

from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError

from termcolor import colored

import settings
import github_translation as translate
from RedmineToGitHub import RedmineToGitHub

from textile_to_markdown import TextileToMarkdown
from repositories_to_migrate import FNAL_REDMINE_REPOS, GITHUB_ORG

import argparse
import time
import os

_FNAL_REDMINE_URL = "https://cdcvs.fnal.gov/redmine/"

_TEXTILE_TO_MARKDOWN = TextileToMarkdown(GITHUB_ORG)

_GREEN_CHECKMARK = colored("\u2714", "green")
_RED_HEAVY_BALLOT_X = colored("\u2718", "red")
_YELLOW_CIRCLE_BULLET = colored("\u25cf", "yellow")


def download_wikis_from(redmine, parsed_args, redmine_repo):
    #redmine_wikis = redmine.project.get(redmine_repo).wiki_pages
    redmine_wikis = redmine.wiki_page.filter(project_id=redmine_repo)

    if not os.path.isdir(f"./redmine/{redmine_repo}"):
        os.mkdir(f"./redmine/{redmine_repo}")

    n_migrated_issues = 0
    n_wikis = len(redmine_wikis)
    width = len(str(n_wikis))

    if n_wikis == 0:
        print(f"\nNo {redmine_repo} wiki pages to download from Redmine")
        return

    if parsed_args.dry_run:
        print(
            f"\nWould download {n_wikis} {redmine_repo} wiki pages from Redmine"
        )
    else:
        print(f"\nDownloading {n_wikis} {redmine_repo} wiki pages from Redmine")

    for i, wiki in enumerate(reversed(redmine_wikis)):
        wiki.export("txt", savepath=f"./redmine/{redmine_repo}", filename=f"{wiki.title}.textile")
        if len(wiki.attachments) > 0:
            print(f"\tDownloading {len(wiki.attachments)} attachments from {wiki.title}")
            for attachment in wiki.attachments:
                attachment.download(savepath=f"./redmine/{redmine_repo}")
        n_migrated_issues += 1

    return n_migrated_issues, n_wikis


def migrate(parsed_args):
    redmine = Redmine(
        _FNAL_REDMINE_URL,
        username=settings.REDMINE_USERNAME,
        key=settings.REDMINE_API_PUBLIC_KEY,
    )

    if not os.path.isdir("./redmine"):
        os.mkdir("./redmine")

    for repo in FNAL_REDMINE_REPOS:
        download_wikis_from(redmine, parsed_args, repo)

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
