"""Set Armenian display names for all users. Run once. Edit the mapping freely."""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])

# Latin name (as stored in `username`)  ->  Armenian display name
ARMENIAN = {
    "Aleksan Azaryan": "Ալեքսան Ազարյան",
    "Aleksandr Mkoyan": "Ալեքսանդր Մկոյան",
    "Aleksandr Motuzov": "Ալեքսանդր Մոտուզով",
    "Andranik Barseghyan": "Անդրանիկ Բարսեղյան",
    "Ani H. Sargsyan": "Անի Հ. Սարգսյան",
    "Ani Hakobyan": "Անի Հակոբյան",
    "Anna Barseghyan": "Աննա Բարսեղյան",
    "Anna G. Kocharyan": "Աննա Գ. Քոչարյան",
    "Ara Hambardzumyan": "Արա Համբարձումյան",
    "Areen Sipan": "Արեն Սիփան",
    "Armen Safaryan": "Արմեն Սաֆարյան",
    "Armine Rehanyan": "Արմինե Ռեհանյան",
    "Arpine Hartenyan": "Արփինե Հարտենյան",
    "Arpine Hovsepyan": "Արփինե Հովսեփյան",
    "Artur Harutyunyan": "Արթուր Հարությունյան",
    "Barouyr Der Haroutounian": "Պարույր Տեր-Հարությունյան",
    "Davit Chaloyan": "Դավիթ Չալոյան",
    "Davit Dashyan": "Դավիթ Դաշյան",
    "Elen Ghalechyan": "Էլեն Ղալեչյան",
    "Eliza Geghamyan": "Էլիզա Գեղամյան",
    "Hakob Melkonyan": "Հակոբ Մելքոնյան",
    "Harutyun Kharberdyan": "Հարություն Խարբերդյան",
    "Hermine Marapyan": "Հերմինե Մարապյան",
    "Karen Harutyunyan": "Կարեն Հարությունյան",
    "Knarik Stepanyan": "Քնարիկ Ստեփանյան",
    "Larisa Ghazaryan": "Լարիսա Ղազարյան",
    "Liana H. Grigoryan": "Լիանա Հ. Գրիգորյան",
    "Liana Manucharyan": "Լիանա Մանուչարյան",
    "Lilit Harutyunyan": "Լիլիթ Հարությունյան",
    "Mane Ghazaryan": "Մանե Ղազարյան",
    "Margarita Avetisyan": "Մարգարիտա Ավետիսյան",
    "Margarita G. Khachatryan": "Մարգարիտա Գ. Խաչատրյան",
    "Maria Manucharyan": "Մարիա Մանուչարյան",
    "Mariam Arzumanyan": "Մարիամ Արզումանյան",
    "Meline Manukyan": "Մելինե Մանուկյան",
    "Milena Margaryan": "Միլենա Մարգարյան",
    "Nare Hakobyan": "Նարե Հակոբյան",
    "Narine Manukyan": "Նարինե Մանուկյան",
    "Nelli Grigoryan": "Նելլի Գրիգորյան",
    "Nune Karapetyan": "Նունե Կարապետյան",
    "Rimma Khlghatyan": "Ռիմմա Խլղաթյան",
    "Robert Martirosyan": "Ռոբերտ Մարտիրոսյան",
    "Ruzanna Yeghiazaryan": "Ռուզաննա Եղիազարյան",
    "Seda Asatryan": "Սեդա Ասատրյան",
    "Seda Kocharyan": "Սեդա Քոչարյան",
    "Seda Margaryan": "Սեդա Մարգարյան",
    "Silva Vardanyan": "Սիլվա Վարդանյան",
    "Sona Khloyan": "Սոնա Խլոյան",
    "Sona L. Harutyunyan": "Սոնա Լ. Հարությունյան",
    "Sona Nazaryan": "Սոնա Նազարյան",
    "Syuzanna Serobyan": "Սյուզաննա Սերոբյան",
    "Tigran Hakobyan": "Տիգրան Հակոբյան",
    "Tigran Mikayelyan": "Տիգրան Միքայելյան",
    "Vahagn Saghatelyan": "Վահագն Սաղաթելյան",
    "Vardan A. Sardaryan": "Վարդան Ա. Սարդարյան",
    "Viktor Ghazaryan": "Վիկտոր Ղազարյան",
    "Vladimir Aghasyan": "Վլադիմիր Աղասյան",
}

users = sb.table("users").select("id, username").execute().data
updated, missing = 0, []
for u in users:
    arm = ARMENIAN.get(u['username'])
    if arm:
        sb.table("users").update({"display_name": arm}).eq("id", u['id']).execute()
        updated += 1
    else:
        missing.append(u['username'])

print(f"Updated Armenian names: {updated}/{len(users)}")
if missing:
    print("No mapping for:", missing)
