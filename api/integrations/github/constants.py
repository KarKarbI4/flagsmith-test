from enum import Enum

GITHUB_API_URL = "https://api.github.com/"
GITHUB_API_VERSION = "2022-11-28"

LINK_FEATURE_TITLE = """**Flagsmith feature linked:** `%s`
Default Values:\n"""
FEATURE_TABLE_HEADER = """| Environment | Enabled | Value | Last Updated (UTC) |
| :--- | :----- | :------ | :------ |\n"""
FEATURE_TABLE_ROW = "| [%s](%s) | %s | %s | %s |\n"
LINK_SEGMENT_TITLE = "Segment `%s` values:\n"
UNLINKED_FEATURE_TEXT = "### The feature flag `%s` was unlinked from the issue/PR"
UPDATED_FEATURE_TEXT = "Flagsmith Feature `%s` has been updated:\n"
DELETED_FEATURE_TEXT = "### The Feature Flag `%s` was deleted"
DELETED_SEGMENT_OVERRIDE_TEXT = (
    "### The Segment Override `%s` for Feature Flag `%s` was deleted"
)
FEATURE_ENVIRONMENT_URL = "%s/project/%s/environment/%s/features?feature=%s&tab=%s"
GITHUB_API_CALLS_TIMEOUT = 10

GITHUB_TAG_COLOR = "#838992"


class GitHubTag(Enum):
    PR_OPEN = "PR Open"
    PR_MERGED = "PR Merged"
    PR_CLOSED = "PR Closed"
    PR_DRAFT = "PR Draft"
    ISSUE_OPEN = "Issue Open"
    ISSUE_CLOSED = "Issue Closed"


github_tag_description = {
    GitHubTag.PR_OPEN.value: "This feature has a linked PR open",
    GitHubTag.PR_MERGED.value: "This feature has a linked PR merged",
    GitHubTag.PR_CLOSED.value: "This feature has a linked PR closed",
    GitHubTag.PR_DRAFT.value: "This feature has a linked PR draft",
    GitHubTag.ISSUE_OPEN.value: "This feature has a linked issue open",
    GitHubTag.ISSUE_CLOSED.value: "This feature has a linked issue closed",
}
