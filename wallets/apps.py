from django.apps import AppConfig


class WalletsConfig(AppConfig):
    name = 'wallets'
    verbose_name = 'Carteiras'

    def ready(self):
        pass
