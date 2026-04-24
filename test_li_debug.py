import os
import requests
from linkedin_api import Linkedin

# Parse all the cookies
raw_cookies = [
    {
        "domain": ".linkedin.com",
        "expirationDate": 1792125360.265237,
        "hostOnly": False,
        "httpOnly": False,
        "name": "bcookie",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": '"v=2&f0f1214d-23bc-477d-840e-0ad315b105b6"'
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1776574785.181605,
        "hostOnly": False,
        "httpOnly": True,
        "name": "__cf_bm",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "aCPiugN8RELV9dZICdXO.UrCdUL1bfkGuvg2kV7yNI0-1776572984.5337865-1.0.1.1-ovZGqV_c7OhgnC12tERLJ0PnT.12TpeRVX3TUQx1uQRi9hrz8aBA_iVOpSlJ3vizgZibGeSjqvzxh6L8LpT_864tPuTFFbSvZLPnOX1f.t2l0jQ0oj.PK77UMEqw322K"
    },
    {
        "domain": "www.linkedin.com",
        "expirationDate": 1779284149.606345,
        "hostOnly": True,
        "httpOnly": False,
        "name": "li_alerts",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "e30="
    },
    {
        "domain": ".linkedin.com",
        "hostOnly": False,
        "httpOnly": True,
        "name": "fptctx2",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "AQESFNDRT0QsJqf9T2bgzBGWVP%252feYCKiIHy%252b3aMzasFrNtIiDVvS6vIe8bRkUl6nN1GQqD4ElN%252fKCrJe792SukuzG08vthQXZBwnEa%252fS%252fvryikTbEk8Xn%252fekft3MCZR%252fukqHPtEkRZ3L9HoN9Cp3PcPbeNSxSDm2Iw6J5cerlq%252bPdqdUFExoeetfSWhOdXktYThVD7N46eobZxL4MlcMyfnkJbOGD%252fuamqtHybpygskerD1WR8hD7Ls6J8LX%252fBx8RHzAE5SX4wyDxnXGIaDzrbD4RJIRfLvRRv9ig808W0dT29Q%252bhnQIUVPkGgQSLmffLCh2c8ALaj1YTFMH1uyi6pAmzsFXLHjx3IH9F3DAg8Sl3%252bNs67F%252fyg9gkItb2kZgHbJdR0YH5odhTUEHneNjNtOf"
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1792124941.154793,
        "hostOnly": False,
        "httpOnly": True,
        "name": "li_at",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "AQEDAWdXAfYAj8sUAAABnaP_wWYAAAGdyAxFZlYAQIQaANV_b3coGZpuFkZ6hcb8ZAsFK6MsBxIB17xjtfUayb4bHws50HdsZM3z_P1ac7tUF2We4iwuQ9B9r9iKsg4k1Ml3K8kexUbKUg7rS1U_qtvQ"
    },
    {
        "domain": ".linkedin.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "lang",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "v=2&lang=en-us"
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1776659341.154941,
        "hostOnly": False,
        "httpOnly": False,
        "name": "lidc",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "\"b=OGST00:s=O:r=O:a=O:p=O:g=3878:u=1:x=1:i=1776572940:t=1776659340:v=2:sig=AQFtCixCrDmiMH3zNszqmqVBEWPPjw68\""
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1792125360.265298,
        "hostOnly": False,
        "httpOnly": True,
        "name": "bscookie",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "\"v=1&202511211219250f608151-033a-4998-88e4-1bcf63054131AQH-up3A0KAmZzAb6Ia61BbETuWE3La3\""
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1779279579.332766,
        "hostOnly": False,
        "httpOnly": True,
        "name": "dfpfpt",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "4734a33060bc486590e3c06576e896b0"
    },
    {
        "domain": ".www.linkedin.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "JSESSIONID",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "ajax:9046869883418971854"
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1792124717.908794,
        "hostOnly": False,
        "httpOnly": True,
        "name": "li_rm",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "AQFTi-YQs0GBxQAAAZ2j_FljeLQkDnwp2iMfZZDAvPgzkyiVWDupRnXIE3xa6JCE5DpYjhiIKlVPYG7Z-cBb_LGqQv7_fTr7fHwvYjfEPXlikBQjjhj08oDTUoj-6rUKq-D0LlqrglvxMCOiWja_Or7ZAcUnuinJv3FTRPmz6txWXIE8GcBULcjFFnWYdpjosDB3UCVCoRKI9zHVwSBRvhESbVO-Mf4shD2nzl9T8dOy5je_UgdU8P5JffrX4XlE6LqAADUuGgjNmeAlxOOu_fTOVbgQTWva97svM9TLvvSjihvRcWtSJwsv03Ynp6M9jYBJLgFAtNiOxT5W_PwjHw"
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1792125297,
        "hostOnly": False,
        "httpOnly": False,
        "name": "li_theme",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "light"
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1792125297,
        "hostOnly": False,
        "httpOnly": False,
        "name": "li_theme_set",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "app"
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1784348941.154731,
        "hostOnly": False,
        "httpOnly": False,
        "name": "liap",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "true"
    },
    {
        "domain": ".www.linkedin.com",
        "expirationDate": 1777782897,
        "hostOnly": False,
        "httpOnly": False,
        "name": "timezone",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "America/Vancouver"
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1779165294.972533,
        "hostOnly": False,
        "httpOnly": True,
        "name": "UserMatchHistory",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "AQL-5w03XH4DhgAAAZ2kBSeIhHWCNG8iLzL7S9868-RYec6HSGFCeO_-KOs6SMTkqCEbKdUaulqAsVZPGOW4bcGIONrB0N3aBfVPWqTai63_GQuXFgX4cQkcmoRTw5HN_a8Lpq904FDXwkkteg9h4qPAHBq_mXMLmzHYBPo9FxfTx0Moi2bZaXcWUxmnTVvek3Hk4caPcfSWTQGS1iaXT-8_gpkBpMMnRAlb4t8OmHA31GfzAN-AReNQn4D3QMvYXRknE12XkZ3rEeRjV-TLwAWj3kCIf7Vxm6M-OxuGaHSO8ScO7ckoEsicSM8VsAIVvIh4hxp1uR5fQoc2x_wZ"
    },
    {
        "domain": ".linkedin.com",
        "expirationDate": 1792124718.07113,
        "hostOnly": False,
        "httpOnly": False,
        "name": "visit",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "v=1&M"
    }
]

cookie_jar = requests.cookies.RequestsCookieJar()
for c in raw_cookies:
    cookie_jar.set(c['name'], c['value'], domain=c['domain'], path=c['path'])

api = Linkedin('a', 'b', authenticate=False)
api.client._set_session_cookies(cookie_jar)

try:
    res = api.get_profile('alex27273')
    print("SUCCESS")
    print(res.keys())
except Exception as e:
    import traceback
    traceback.print_exc()

