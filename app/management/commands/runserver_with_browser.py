import os
from django.core.management.commands.runserver import Command as RunserverCommand
import webbrowser

class Command(RunserverCommand):
    def on_bind(self, server_port):
        super().on_bind(server_port)
        if os.name == "posix" : return 
        webbrowser.open(f"http://127.0.0.1:{server_port}/app/orders") 

