from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'
    verbose_name = 'Usuários'

    def ready(self):
        import users.signals  # noqa: F401
