import secrets
import string
import csv

raw_users = """Aleksan Azaryan <Aleksan.Azaryan@ameriabank.am>; Aleksandr Mkoyan <Aleksandr.Mkoyan@ameriabank.am>; Aleksandr Motuzov <Aleksandr.Motuzov@ameriabank.am>; Andranik Barseghyan <A.Barseghyan@ameriabank.am>; Ani H. Sargsyan <Ani.h.Sargsyan@ameriabank.am>; Ani Hakobyan <Ani.Hakobyan@ameriabank.am>; Anna Barseghyan <Anna.Barseghyan@ameriabank.am>; Anna G. Kocharyan <Anna.G.Kocharyan@ameriabank.am>; Ara Hambardzumyan <ar.hambardzumyan@ameriabank.am>; Areen Sipan <Areen.Sipan@ameriabank.am>; Armen Safaryan <Armen.Safaryan@ameriabank.am>; Armine Rehanyan <Armine.Rehanyan@ameriabank.am>; Arpine Hartenyan <Arpine.Hartenyan@ameriabank.am>; Arpine Hovsepyan <Arpine.Hovsepyan@ameriabank.am>; Artur Harutyunyan <Artur.Harutyunyan@ameriabank.am>; Barouyr Der Haroutounian <Barouyr.Der.Haroutounian@ameriabank.am>; Davit Chaloyan <Davit.Chaloyan@ameriabank.am>; Davit Dashyan <D.Dashyan@ameriabank.am>; Elen Ghalechyan <Elen.Ghalechyan2@ameriabank.am>; Eliza Geghamyan <Eliza.Geghamyan@ameriabank.am>; Hakob Melkonyan <Hakob.Melkonyan@ameriabank.am>; Harutyun Kharberdyan <Harutyun.Kharberdyan@ameriabank.am>; Hermine Marapyan <Hermine.Marapyan@ameriabank.am>; Karen Harutyunyan <Karen.Harutyunyan@ameriabank.am>; Knarik Stepanyan <Knarik.Stepanyan@ameriabank.am>; Larisa Ghazaryan <Larisa.Ghazaryan@ameriabank.am>; Liana H. Grigoryan <Liana.Grigoryan2@ameriabank.am>; Liana Manucharyan <L.Manucharyan@ameriabank.am>; Lilit Harutyunyan <Lilit.Harutyunyan@ameriabank.am>; Mane Ghazaryan <Mane.Ghazaryan@ameriabank.am>; Margarita Avetisyan <Margarita.Avetisyan@ameriabank.am>; Margarita G. Khachatryan <Margarita.G.Khachatryan@ameriabank.am>; Maria Manucharyan <Maria.Manucharyan@ameriabank.am>; Mariam Arzumanyan <M.Arzumanyan@ameriabank.am>; Meline Manukyan <Meline.Manukyan@ameriabank.am>; Milena Margaryan <Milena.Margaryan@ameriabank.am>; Nare Hakobyan <Nare.Hakobyan@ameriabank.am>; Narine Manukyan <Narine.Manukyan@ameriabank.am>; Nelli Grigoryan <Nelli.Grigoryan@ameriabank.am>; Nune Karapetyan <Nune.Karapetyan@ameriabank.am>; Rimma Khlghatyan <R.Khlghatyan@ameriabank.am>; Robert Martirosyan <Robert.Martirosyan@ameriabank.am>; Ruzanna Yeghiazaryan <Ruzanna.Yeghiazaryan@ameriabank.am>; Seda Asatryan <Seda.Asatryan@ameriabank.am>; Seda Kocharyan <Seda.Kocharyan@ameriabank.am>; Seda Margaryan <Seda.Margaryan@ameriabank.am>; Silva Vardanyan <Silva.Vardanyan@ameriabank.am>; Sona Khloyan <Sona.Khloyan@ameriabank.am>; Sona L. Harutyunyan <Sona.L.Harutyunyan@ameriabank.am>; Sona Nazaryan <Sona.Nazaryan@ameriabank.am>; Syuzanna Serobyan <Syuzanna.Serobyan@ameriabank.am>; Tigran Hakobyan <Tigran.Hakobyan@ameriabank.am>; Tigran Mikayelyan <Tigran.Mikayelyan@ameriabank.am>; Vahagn Saghatelyan <V.Saghatelyan@ameriabank.am>; Vardan A. Sardaryan <Vardan.A.Sardaryan@ameriabank.am>; Viktor Ghazaryan <Viktor.Ghazaryan@ameriabank.am>; Vladimir Aghasyan <Vladimir.Aghasyan@ameriabank.am>"""

def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

users_data = []
for entry in raw_users.split(';'):
    if '<' in entry:
        name_part, email_part = entry.split('<')
        name = name_part.strip()
        email = email_part.replace('>', '').strip()
        password = generate_password()
        users_data.append({'Name': name, 'Email': email, 'Password': password})

with open('ameria_credentials.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['Name', 'Email', 'Password'])
    writer.writeheader()
    writer.writerows(users_data)

print(f"Generated credentials for {len(users_data)} users.")
