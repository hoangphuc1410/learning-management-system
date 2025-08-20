from django.apps import AppConfig


class UserauthsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'userauths'

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver.
        import userauths.signals
