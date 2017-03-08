#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Python client library for the Facebook Platform.

This client library is designed to support the Graph API and the official
Facebook JavaScript SDK, which is the canonical way to implement
Facebook authentication. Read more about the Graph API at
http://developers.facebook.com/docs/api. You can download the Facebook
JavaScript SDK at http://github.com/facebook/connect-js/.

If your application is using Google AppEngine's webapp framework, your
usage of this module might look like this:

    user = facebook.get_user_from_cookie(self.request.cookies, key, secret)
    if user:
        graph = facebook.GraphAPI(user["access_token"])
        profile = graph.get_object("me")
        friends = graph.get_connections("me", "friends")

"""

import cgi
import hashlib
import time
import urllib
import random
import mimetypes
import httplib
import requests

# Find a JSON parser
# try:
#     import json
#     _parse_json = lambda s: json.loads(s)
# except ImportError:
try:
    import simplejson
    _parse_json = lambda s: simplejson.loads(s)
except ImportError:
    # For Google AppEngine
    from django.utils import simplejson
    _parse_json = lambda s: simplejson.loads(s)


FB_ISO_8601 = '%Y-%m-%dT%H:%M:%S%z'


class GraphAPI(object):
    """A client for the Facebook Graph API.

    See http://developers.facebook.com/docs/api for complete documentation
    for the API.

    The Graph API is made up of the objects in Facebook (e.g., people, pages,
    events, photos) and the connections between them (e.g., friends,
    photo tags, and event RSVPs). This client provides access to those
    primitive types in a generic way. For example, given an OAuth access
    token, this will fetch the profile of the active user and the list
    of the user's friends:

       graph = facebook.GraphAPI(access_token)
       user = graph.get_object("me")
       friends = graph.get_connections(user["id"], "friends")

    You can see a list of all of the objects and connections supported
    by the API at http://developers.facebook.com/docs/reference/api/.

    You can obtain an access token via OAuth or by using the Facebook
    JavaScript SDK. See http://developers.facebook.com/docs/authentication/
    for details.

    If you are using the JavaScript SDK, you can use the
    get_user_from_cookie() method below to get the OAuth access token
    for the active user from the cookie saved by the SDK.
    """

    def __init__(self, access_token=None, version=None, timeout=None, session=None):
        self.access_token = access_token
        self.version = version
        self.host = "graph.facebook.com/"
        self.url = "https://{}/".format(
            self.host
        ) if not self.version else "https://{0}{1}/".format(
            self.host, self.version
        )
        self.timeout = timeout
        self.session = session or requests.session()

    def get_object(self, id, **args):
        """Fetchs the given object from the graph."""
        return self.request(id, args)

    def get_objects(self, ids, **args):
        """Fetchs all of the given object from the graph.

        We return a map from ID to object. If any of the IDs are invalid,
        we raise an exception.
        """
        args["ids"] = ",".join(ids)
        return self.request("", args)

    def get_connections(self, id, connection_name, **args):
        """Fetchs the connections for given object."""
        return self.request(id + "/" + connection_name, args)

    def put_object(self, parent_object, connection_name, **data):
        """Writes the given object to the graph, connected to the given parent.

        For example,

            graph.put_object("me", "feed", message="Hello, world")

        writes "Hello, world" to the active user's wall. Likewise, this
        will comment on a the first post of the active user's feed:

            feed = graph.get_connections("me", "feed")
            post = feed["data"][0]
            graph.put_object(post["id"], "comments", message="First!")

        See http://developers.facebook.com/docs/api#publishing for all of
        the supported writeable objects.

        Most write operations require extended permissions. For example,
        publishing wall posts requires the "publish_stream" permission. See
        http://developers.facebook.com/docs/authentication/ for details about
        extended permissions.
        """
        assert self.access_token, "Write operations require an access token"
        return self.request(
            '{0}/{1}'.format(parent_object, connection_name),
            post_args=data,
            method='POST',
        )

    def put_wall_post(self, message, attachment={}, profile_id="me"):
        """Writes a wall post to the given profile's wall.

        We default to writing to the authenticated user's wall if no
        profile_id is specified.

        attachment adds a structured attachment to the status message being
        posted to the Wall. It should be a dictionary of the form:

            {"name": "Link name"
             "link": "http://www.example.com/",
             "caption": "{*actor*} posted a new review",
             "description": "This is a longer description of the attachment",
             "picture": "http://www.example.com/thumbnail.jpg"}

        """
        return self.put_object(profile_id, "feed", message=message, **attachment)

    def get_page_access_token(self, page_id, fb_uid):
        """Get the access_token for this page."""
        # Posts to Pages require their own access token. See:
        # https://developers.facebook.com/docs/pages/access-tokens
        #
        # If a page_id is provided, fetch account information for this
        # facebook user and fetch the access_token that corresponds with
        # the page_id.
        page_access_token = None
        url = '{url}{fb_uid}/accounts'.format(
            url=self.url,
            fb_uid=fb_uid,
        )
        account_response = requests.get(
            url,
            params={'access_token': self.access_token}
        )
        account_data = account_response.json()

        if account_response.status_code != 200:
            error_message = account_data.get('error').get('message')
            return page_access_token, error_message

        accounts = account_data.get('data')
        for account in accounts:
            if account['id'] == page_id:
                page_access_token = account['access_token']

        return page_access_token, None

    def put_event(self, id=None, page_id=None, fb_uid=None, **data):
        """Creates an event with a picture.

        We accept the params as per
        http://developers.facebook.com/docs/reference/api/event
        However, we also accept a picture param, which should point to
        a URL for the event image.

        """

        if id:
            path = '%s' % id
        elif page_id:
            path = '%s/events' % page_id
        else:
            path = 'me/events'

        response = self.request(path, post_args=data, method='POST')

        if 'picture' in data and isinstance(response, dict) and 'id' in response:
            page_access_token = None
            if page_id and fb_uid:
                page_access_token, error_message = self.get_page_access_token(
                    page_id,
                    fb_uid
                )
                if error_message:
                    return response, error_message

            # Upload the event picture to the facebook event
            post_args = {}
            post_args['cover_url'] = data['picture']
            if page_access_token:
                post_args['access_token'] = page_access_token
            else:
                post_args['access_token'] = self.access_token

            url = '{url}{id}/'.format(
                url=self.url,
                id=response['id'],
            )
            picture_response = requests.post(url, data=post_args)

            # If there's an error, return the message to the calling code so we
            # can log it. Not raising a GraphAPIError here because we want the
            # event to publish even if there is an error in uploading the
            # picture.
            if picture_response.status_code != 200:
                json_response = picture_response.json()
                error_message = json_response.get('error').get('message')
                return response, error_message

        return response, None

    def put_comment(self, object_id, message):
        """Writes the given comment on the given post."""
        return self.put_object(object_id, "comments", message=message)

    def put_like(self, object_id):
        """Likes the given post."""
        return self.put_object(object_id, "likes")

    def delete_object(self, id):
        """Deletes the object with the given ID from the graph."""
        return self.request(id, method='DELETE')

    def get_permissions(self, id):
        """Takes a Facebook user ID and returns a dict of perms.

        The dictionary is composed of all the permissions the current
        facebook app has been granted by the user, in the form of:

            {
                'user_location': True,
                'user_groups': True,
                'public_profile': True,
                'user_friends': True,
                ...,
            }
        """
        args = {
            'access_token': self.access_token
        }
        path = "{}/permissions".format(id)

        data = self.request(path)
        perms = {}
        for permission in data.get('data'):
            perms[permission['permission']] = True if permission['status'] == 'granted' else False

        return perms

    def request(self, path, args=None, post_args=None, method=None):
        """Fetches the given path in the Graph API.

        We translate args to a valid query string. If post_args is given,
        we send a POST request to the given path with the given arguments.
        """
        if not args: args = {}
        if post_args is not None:
            method='POST'

        if self.access_token:
            # If post_args exists, we assume that args either does not exists
            # or it does not need `access_token`.
            if post_args and 'access_token' not in post_args:
                post_args['access_token'] = self.access_token
            elif 'access_token' not in args:
                args['access_token'] = self.access_token

        try:
            response = self.session.request(
                method=method or 'GET',
                url='{0}{1}'.format(self.url, path),
                params=args,
                data=post_args,
                timeout=self.timeout,
            )
        except requests.HTTPError as e:
            error_response = _parse_json(e.read()) or {}
            raise GraphAPIError(
                type=error_response.get('error', {}).get('type'),
                message=error_response.get('error', {}).get('message')
            )

        result = response.json()

        if result.get('error'):
            error_response = result.get('error')
            raise GraphAPIError(
                type=error_response.get('type'),
                message=error_response.get('message')
            )

        return result

    def multipart_request(self, path, args=None, post_args=None, files=None):
        """Request a given path in the Graph API with multipart support.

        If post_args or files is given, we send a POST multipart request.

        files is a dict of {'filename.ext', 'value'} of files to upload.
        """
        def __encode_multipart_data(post_args, files):
            boundary = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz' \
                'ABCDEFGHIJKLMNOPQRSTUVWXYZ') for ii in range(31))

            def get_content_type(filename):
                return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

            def encode_field(field_name, value):
                return ('--' + boundary,
                        'Content-Disposition: form-data; name="%s"' % field_name,
                        '', str(value))

            def encode_file(filename, value):
                return ('--' + boundary,
                        'Content-Disposition: form-data; filename="%s"' % (filename, ),
                        'Content-Type: %s' % get_content_type(filename),
                        '', value)

            lines = []
            for (field_name, value) in post_args.items():
                lines.extend(encode_field(field_name, value))
            for (filename, value) in files.items():
                lines.extend(encode_file(filename, value))
            lines.extend(('--%s--' % boundary, ''))
            body = '\r\n'.join(lines)

            headers = {'content-type': 'multipart/form-data; boundary=' + boundary,
                       'content-length': str(len(body))}

            return body, headers

        if not args: args = {}
        if self.access_token:
            if post_args is not None:
                post_args["access_token"] = self.access_token
            else:
                args["access_token"] = self.access_token

        path = path + "?" + urllib.urlencode(args)
        connection = httplib.HTTPSConnection("graph.facebook.com")
        method = "POST" if post_args or files else "GET"
        connection.request(method, path,
                            *__encode_multipart_data(post_args, files))
        http_response = connection.getresponse()
        try:
            response = _parse_json(http_response.read())
        finally:
            http_response.close()
            connection.close()
        if isinstance(response, dict) and response.get("error"):
            raise GraphAPIError(response["error"]["type"],
                                response["error"]["message"])
        return response


class GraphAPIError(Exception):
    def __init__(self, type, message):
        Exception.__init__(self, message)
        self.type = type


class FQLAPI(object):
    """
    A client for the Facebook FQL API.

    See http://developers.facebook.com/docs/reference/fql/ for complete documentation
    for the API.

    The Graph API is made up of the objects in Facebook (e.g., people, pages,
    events, photos) and the connections between them (e.g., friends,
    photo tags, and event RSVPs). This client provides access to those
    primitive types in an advanced way. For example, given an OAuth access
    token, this will fetch the profile of the active user and list the user's
    friend's profile pictures.

        graph = facebook.GraphAPI(access_token)
        user = graph.get_object("me")
        fql = facebook.FQLAPI(access_token)
        friends = fql.query("SELECT pic_small FROM profile where id in (SELECT uid2 from friend where uid1 = " + user["id"] + ")")


    You can see a list of all of the objects and connections supported
    by the API at http://developers.facebook.com/docs/reference/fql/.

    You can obtain an access token via OAuth or by using the Facebook
    JavaScript SDK. See http://developers.facebook.com/docs/authentication/
    for details.

    If you are using the JavaScript SDK, you can use the
    get_user_from_cookie() method below to get the OAuth access token
    for the active user from the cookie saved by the SDK.
    """

    def __init__(self, access_token):
        self.access_token = access_token

    def query(self, query):
        """ Performs a FQL query on Facebook. Just a wrapper around the `request`
        method below. """
        return self.request(query)

    def request(self, query):
        """ Performs the given query on Facebook or raises an `FQLAPIError` """

        file = urllib.urlopen('https://api.facebook.com/method/fql.query?access_token=%s&format=json&query=%s' % (
            urllib.quote_plus(self.access_token), urllib.quote_plus(query)))
        try:
            response = _parse_json(file.read())
        finally:
            file.close()

        if isinstance(response, dict) and response.get('error_code'):
            raise FQLAPIError(response['error_code'], response['error_msg'])

        return response


class FQLAPIError(Exception):
    def __init__(self, type, message):
        Exception.__init__(self, message)
        self.type = type


def get_user_from_cookie(cookies, app_id, app_secret):
    """Parses the cookie set by the official Facebook JavaScript SDK.

    cookies should be a dictionary-like object mapping cookie names to
    cookie values.

    If the user is logged in via Facebook, we return a dictionary with the
    keys "uid" and "access_token". The former is the user's Facebook ID,
    and the latter can be used to make authenticated requests to the Graph API.
    If the user is not logged in, we return None.

    Download the official Facebook JavaScript SDK at
    http://github.com/facebook/connect-js/. Read more about Facebook
    authentication at http://developers.facebook.com/docs/authentication/.
    """
    cookie = cookies.get("fbs_" + app_id, "")
    if not cookie: return None
    args = dict((k, v[-1]) for k, v in cgi.parse_qs(cookie.strip('"')).items())
    payload = "".join(k + "=" + args[k] for k in sorted(args.keys())
                      if k != "sig")
    sig = hashlib.md5(payload + app_secret).hexdigest()
    expires = int(args["expires"])
    if sig == args.get("sig") and (expires == 0 or time.time() < expires):
        return args
    else:
        return None
