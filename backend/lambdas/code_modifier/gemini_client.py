# import json
# import urllib.request
# import urllib.error

# MODEL = "gemini-3.8-flash"

# def call_gemini(prompt, api_key, json_output=False, timeout=45):
#     url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
#     body = {
#         "contents": [{"parts": [{"text": prompt}]}],
#         "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
#     }
#     if json_output:
#         body["generationConfig"]["responseMimeType"] = "application/json"

#     req = urllib.request.Request(
#         url,
#         data=json.dumps(body).encode("utf-8"),
#         headers={"Content-Type": "application/json"},
#         method="POST"
#     )
#     try:
#         with urllib.request.urlopen(req, timeout=timeout) as resp:
#             data = json.loads(resp.read().decode("utf-8"))
#     except urllib.error.HTTPError as e:
#         raise RuntimeError(f"Gemini HTTP {e.code}: {e.read().decode('utf-8')}")
#     except urllib.error.URLError as e:
#         raise RuntimeError(f"Gemini network error: {e}")

#     try:
#         text = data["candidates"][0]["content"]["parts"][0]["text"]
#     except (KeyError, IndexError):
#         raise RuntimeError(f"Unexpected Gemini response shape: {data}")

#     if json_output:
#         return json.loads(text)
#     return text


# def get_secret(secret_name, region):
#     import boto3
#     client = boto3.client("secretsmanager", region_name=region)
#     resp = client.get_secret_value(SecretId=secret_name)
#     return json.loads(resp["SecretString"])

import json
import time
import urllib.request
import urllib.error


MODEL = "gemini-flash-lite-latest"

def call_gemini(prompt, api_key, json_output=False, timeout=45, max_retries=3):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192}
    }
    if json_output:
        body["generationConfig"]["responseMimeType"] = "application/json"

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8")
            last_error = RuntimeError(f"Gemini HTTP {e.code}: {body_text}")
            if e.code in (429, 503) and attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise last_error
        except urllib.error.URLError as e:
            last_error = RuntimeError(f"Gemini network error: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            raise last_error
    else:
        raise last_error

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected Gemini response shape: {data}")

    if json_output:
        return json.loads(text)
    return text


def get_secret(secret_name, region):
    import boto3
    client = boto3.client("secretsmanager", region_name=region)
    resp = client.get_secret_value(SecretId=secret_name)
    return json.loads(resp["SecretString"])