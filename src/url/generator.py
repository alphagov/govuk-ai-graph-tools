import urllib.parse
from typing import Optional


def convert_string_to_url_query_format(text: str) -> str:
    quoted = urllib.parse.quote(text, safe="")
    quoted = quoted.replace("-", "%2D").replace(".", "%2E").replace("~", "%7E").replace("_", "%5F")
    return quoted


def generate_url_fragement(base_url: str, content: str):
    encoded_content = convert_string_to_url_query_format(content)
    url = f"{base_url}#:~:text={encoded_content}"
    return url


def s3_to_govuk_url(s3_uri: str, url_map: Optional[dict] = None) -> str:
    """
    Derives a GOV.UK URL from an S3 URI, using url_map if provided,
    otherwise using fallback logic.
    """
    if url_map and s3_uri in url_map:
        return url_map[s3_uri]

    if "/input/" in s3_uri:
        path = s3_uri.split("/input/")[-1]
    else:
        path = s3_uri.split("/")[-1]

    path = path.replace(".md", "")
    return f"https://www.gov.uk/{path}"
