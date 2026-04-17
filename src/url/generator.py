import urllib.parse

def convert_string_to_url_query_format(text: str):
    # For GOV.UK text fragments (#:~:text=), characters like '-' are reserved
    # syntax characters and must be percent-encoded. 
    # Python's urllib.parse.quote never quotes '-', '.', '_', or '~'.
    # So we manually encode '-' to ensure it works with text fragments.
    quoted = urllib.parse.quote(text, safe='')
    return quoted.replace('-', '%2D')

def generate_url_fragement(base_url: str, content: str):
    encoded_content = convert_string_to_url_query_format(content)
    url = f"{base_url}#:~:text={encoded_content}"
    return url

def s3_to_govuk_url(s3_uri: str) -> str:
    """Derives a GOV.UK URL directly from an S3 URI by stripping the prefix and extension."""
    if "/input/" in s3_uri:
        path = s3_uri.split("/input/")[-1]
    else:
        path = s3_uri.split("/")[-1]
        
    path = path.replace(".md", "")
    return f"https://www.gov.uk/{path}"

    
