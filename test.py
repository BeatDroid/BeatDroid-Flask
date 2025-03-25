TrackMetadata(name='Apocalypse', artist='Cigarettes After Sex', album='Cigarettes After Sex', released='June 09, 2017', duration='04:50', image='https://i.scdn.co/image/ab67616d0000b273dfed999f959177dfc4f33cdc', label='Partisan Records', id='1oAwsWBovWRIp7qLMGPIet')

TrackMetadata(name='The Night We Met', artist='Lord Huron', album='Strange Trails', released='April 06, 2015', duration='03:28', image='https://i.scdn.co/image/ab67616d0000b27317875a0610c23d8946454583', label='Play It Again Sam', id='3hRV0jL3vUpRrcy398teAU')

import unittest
from app import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_health_check(self):
        response = self.app.get('/hello')
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello, World!", response.get_data(as_text=True))

    def test_missing_env_variables(self):
        # Simulate missing environment variables
        with self.assertRaises(EnvironmentError):
            app.config['SPOTIFY_CLIENT_ID'] = None
            app.config['SPOTIFY_CLIENT_SECRET'] = None

if __name__ == "__main__":
    unittest.main()