"""Small Jev HTTP client. No SDK, generated text, or automatic retries."""
import json
import math
import os
import urllib.error
import urllib.request

URL = 'https://api.typesafe.ai/v1/systemone'
MODEL = 'jev-1.14.0'


class JevError(Exception):
    def __init__(self, message, http_status=None):
        super().__init__(message)
        self.http_status = http_status


def validate(response):
    if response.get('model') != MODEL:
        raise ValueError('Response did not use the pinned Jev version')
    answer = response['answers']['verdict']
    probabilities = answer['probabilities']
    if answer['type'] != 'choice' or set(probabilities) != set('ABCD'):
        raise ValueError('Expected a choice with exactly A, B, C, D')
    values = list(probabilities.values())
    if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError('Invalid probability')
    if not math.isclose(sum(values), 1, abs_tol=1e-5):
        raise ValueError('Probabilities do not sum to one')
    # Alphabetical order breaks exact ties consistently with our GLiDE scorer.
    winner = max('ABCD', key=probabilities.get)
    choice = answer['choice']
    if choice not in probabilities or probabilities[choice] != probabilities[winner]:
        raise ValueError('API choice is not a highest-probability option')
    usage = response['usage']
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens', 'output_tokens')):
        raise ValueError('Missing or invalid token usage')
    return {'probabilities': probabilities, 'letter': winner, 'detected': winner == 'A',
            'api_choice': choice, 'usage': usage}


def decide(request, long_context=False, timeout=600):
    key = os.environ.get('TYPESAFE_API_KEY')
    if not key:
        raise JevError('TYPESAFE_API_KEY is not set; no request was sent')
    if set(request) != {'state', 'questions'} or set(request['questions']) != {'verdict'}:
        raise ValueError('Only the prepared state and verdict question may be sent')
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
    if long_context:
        headers['TypeSafe-Danger-Zone-Long-Context'] = 'true'
    body = json.dumps({'model': MODEL, **request}, ensure_ascii=False).encode('utf-8')
    # Request creates the POST; urlopen sends it. The key is never written to disk.
    post = urllib.request.Request(URL, data=body, headers=headers, method='POST')
    # Reject redirects so authentication cannot be forwarded to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(post, timeout=timeout) as result:
            response = json.load(result)
    except urllib.error.HTTPError as error:
        # Do not log the server body: it could echo the input or credentials.
        raise JevError(f'Jev HTTP {error.code}; request was not retried', error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise JevError('Transport failure; the server may have processed the request. Not retried.') from None
    except (ValueError, UnicodeError):
        raise JevError('Jev returned invalid JSON; not retried') from None
    try:
        result = validate(response)
    except (ValueError, TypeError, KeyError):
        raise JevError('Invalid Jev response; not counted as a negative judgment') from None
    return {**result, 'response': response}
