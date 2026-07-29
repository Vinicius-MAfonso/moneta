from django.test import TestCase

from django.contrib.auth import get_user_model


class UserModelTests(TestCase):
    def test_superuser_has_audit_timestamps(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='Password123!'
        )

        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)
