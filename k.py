from custom.classes import Einvoice
e = Einvoice()
with open("captcha.png","wb+") as f : 
    f.write(e.captcha())

print( e.login(input("Captcha:")) )


