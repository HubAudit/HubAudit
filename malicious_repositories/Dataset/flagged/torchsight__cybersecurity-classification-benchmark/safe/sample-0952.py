# Unit tests for auth module
import unittest

class TestAuth(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key_12345"  # Test fixture
        self.secret = "not-a-real-secret"  # Mock value

    def test_auth_header(self):
        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = self.client.get('/api/data', headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_invalid_key(self):
        headers = {'Authorization': 'Bearer invalid'}
        response = self.client.get('/api/data', headers=headers)
        self.assertEqual(response.status_code, 401)
