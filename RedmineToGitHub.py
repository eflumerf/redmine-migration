from tabulate import tabulate

import time


class RedmineToGitHub:
    def __init__(self, gh, github_logins={}):
        self._gh = gh
        self._translation = github_logins

    def gh_login(self, redmine_username):
        return self._translation.get(redmine_username)

    def _search(self, query):
        # To avoid rate limits
        time.sleep(3)
        users = self._gh.search_users(query)
        return users[0].login if users.totalCount == 1 else None

    def search_for_login(self, redmine_username, mail):
        if mail is not None:
            login = self._search(f"{mail} in:email")
            if login is not None:
                return self._translation.setdefault(redmine_username, login)

        # Either mail is None or lookup by mail failed.  Try with the fullname.
        login = self._search(f"fullname:{redmine_username}")
        return self._translation.setdefault(redmine_username, login)

    def table(self):
        return tabulate(
            [[key, value] for key, value in sorted(self._translation.items())],
            headers=["Redmine name", "GitHub login"],
        )
