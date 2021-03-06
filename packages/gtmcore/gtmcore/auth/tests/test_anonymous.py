import pytest
import responses

from gtmcore.fixtures.auth import mock_config_file_with_auth_anonymous
from gtmcore.auth.identity import get_identity_manager_class, AuthenticationError
from gtmcore.auth.anonymous import AnonymousIdentityManager
from gtmcore.auth import User


ANON_TOKEN = "R0lHQU5UVU0tQU5PTllNT1VTLVVTRVI=.VVVJRDEyMzQ1Njc4OTA=.R0lHQU5UVU0tQU5PTllNT1VTLVVTRVI="


class TestIdentityAnonymous(object):
    def test_is_session_valid(self, mock_config_file_with_auth_anonymous):
        """test check for valid session"""
        config_instance, tokens, work_dir = mock_config_file_with_auth_anonymous
        mgr = get_identity_manager_class(config_instance)(config_instance)
        assert type(mgr) == AnonymousIdentityManager

        # Invalid with no token
        assert mgr.is_token_valid() is False
        assert mgr.is_token_valid(None) is False

        # Junk base64 encoded data should be False too
        assert mgr.is_token_valid("YXNkZmFzZGZhc2Rm") is False

        # A proper "anonymous" bearer token will be considered valid
        assert mgr.is_token_valid(ANON_TOKEN) is True

        # You should also be able to log in with a valid token
        assert mgr.is_token_valid(tokens['access_token']) is True
        assert mgr.rsa_key is not None

    def test_is_authenticated_token(self, mock_config_file_with_auth_anonymous):
        """test checking if the user is authenticated via a token"""
        config_instance, tokens, work_dir = mock_config_file_with_auth_anonymous
        mgr = get_identity_manager_class(config_instance)(config_instance)
        assert type(mgr) == AnonymousIdentityManager

        # Invalid with no token
        assert mgr.is_authenticated() is False
        assert mgr.is_authenticated(None) is False
        assert mgr.is_authenticated(tokens['access_token']) is True

        # Second access should fail since not cached
        mgr2 = get_identity_manager_class(config_instance)(config_instance)
        assert mgr2.is_authenticated() is False

    @responses.activate
    def test_get_user_profile(self, mock_config_file_with_auth_anonymous):
        """test getting a user profile from Auth0"""
        responses.add(responses.POST, 'https://test.gigantum.com/api/v1/',
                      json={'data': {'synchronizeUserAccount': {'gitUserId': "123"}}},
                      status=200)

        config_instance, tokens, work_dir = mock_config_file_with_auth_anonymous
        mgr = get_identity_manager_class(config_instance)(config_instance)
        assert type(mgr) == AnonymousIdentityManager

        # Load User
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr.get_user_profile()

        # Load User
        u = mgr.get_user_profile(tokens['access_token'],
                                 tokens['id_token'])
        assert type(u) == User
        assert u.username == "johndoe"
        assert u.email == "john.doe@gmail.com"
        assert u.given_name == "John"
        assert u.family_name == "Doe"

        # Second access should fail since not cached
        mgr2 = get_identity_manager_class(config_instance)(config_instance)
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr2.get_user_profile()

    def test_get_anon_user_profile(self, mock_config_file_with_auth_anonymous):
        """test getting a user profile when anonymous"""
        config_instance, tokens, work_dir = mock_config_file_with_auth_anonymous
        mgr = get_identity_manager_class(config_instance)(config_instance)
        assert type(mgr) == AnonymousIdentityManager

        # Load User
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr.get_user_profile()

        # Load User
        u = mgr.get_user_profile(ANON_TOKEN,
                                 "wedontcareabouttheidtokenbutithastoexist")
        assert type(u) == User
        assert u.username == "anonymous"
        assert u.email == "anonymous@gigantum.com"
        assert u.given_name == "Anonymous"
        assert u.family_name == "User"

        # Second access should fail since not cached
        mgr2 = get_identity_manager_class(config_instance)(config_instance)
        with pytest.raises(AuthenticationError):
            # Should fail without a token
            mgr2.get_user_profile()
