# from django.core.management.commands.runserver import Command as BaseRunCommand
# import webbrowser

# class Command(BaseRunCommand):
#     def on_bind(self, server_port):
#         addr = "0.0.0.0" if self.addr == "0" else self.addr         
#         url = f"{self.protocol}://{addr}:{server_port}/"
#         webbrowser.open(url)
#         return super().on_bind(server_port)
