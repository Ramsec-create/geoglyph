import json
from pathlib import Path

# Extracted from NASA "Your Name in Landsat" JS bundle
# Each entry: (letter, variant, title, coords_short, coords_link)
LOCATIONS = {
    "a_0.jpg": ("Hickman, Kentucky", "36°35'20.8 N 89°20'26.9 W"),
    "a_1.jpg": ("Farm Island, Maine", "45°43'43.8 N 69°46'08.9 W"),
    "a_2.jpg": ("Lake Guakhmaz, Azerbaijan", "40°39'50.8 N 47°06'36.2 E"),
    "a_3.jpg": ("Yukon Delta, Alaska", "62°33'17.7 N 164°56'10.3 W"),
    "a_4.jpg": ("Lake Mjøsa, Norway", "60°45'52.7 N 10°56'43.2 E"),
    "b_0.jpg": ("Holla Bend, Arkansas", "35°08'41.1 N 93°03'16.5 W"),
    "b_1.jpg": ("Humaitá, Brazil", "7°37'00.1 S 62°55'17.0 W"),
    "c_0.jpg": ("Black Rock Desert, Nevada", "40°47'15.8 N 119°12'13.0 W"),
    "c_1.jpg": ("Deception Island, Antarctica", "62°57'22.3 S 60°38'32.8 W"),
    "c_2.jpg": ("False River, Louisiana", "30°38'39.7 N 91°26'45.7 W"),
    "d_0.jpg": ("Akimiski Island, Canada", "53°00'58.5 N 81°18'24.6 W"),
    "d_1.jpg": ("Lake Tandou, Australia", "32°37'17.8 S 142°04'21.4 E"),
    "e_0.jpg": ("Firn-filled Fjords, Tibet", "29°15'46.9 N 96°19'03.8 E"),
    "e_1.jpg": ("Sea of Okhotsk", "54°42'50.3 N 136°34'20.4 E"),
    "e_2.jpg": ("Bellona Plateau", "20°30'00.0 S 158°30'00.0 E"),
    "e_3.jpg": ("Breiðamerkurjökull Glacier, Iceland", "64°05'45.0 N 16°21'45.6 W"),
    "f_0.jpg": ("Mato Grosso, Brazil", "13°50'26.9 S 55°17'55.0 W"),
    "f_1.jpg": ("Kruger National Park, South Africa", "28°44'01.3 S 29°12'30.1 E"),
    "g_0.jpg": ("Fonte Boa, Amazonas", "2°26'30.8 S 66°16'43.7 W"),
    "h_0.jpg": ("Southwestern Kyrgyzstan", "40°14'03.6 N 71°14'22.8 E"),
    "h_1.jpg": ("Khorinsky District, Russia", "52°02'50.4 N 109°46'51.2 E"),
    "i_0.jpg": ("Borgarbyggð, Iceland", "64°45'46.4 N 22°27'28.0 W"),
    "i_1.jpg": ("Canandaigua Lake, New York", "42°47'11.0 N 77°42'58.1 W"),
    "i_2.jpg": ("Etosha National Park, Namibia", "18°29'15.2 S 16°10'14.6 E"),
    "i_3.jpg": ("Djebel Ouarkziz, Morocco", "28°18'01.5 N 10°33'58.5 W"),
    "i_4.jpg": ("Holuhraun Ice Field, Iceland", "64°51'11.2 N 16°49'37.2 W"),
    "j_0.jpg": ("Great Barrier Reef", "18°20'55.3 S 146°50'51.4 E"),
    "j_1.jpg": ("Karakaya Dam, Turkey", "38°29'37.7 N 38°26'39.5 E"),
    "j_2.jpg": ("Lake Superior, North America", "46°41'10.2 N 90°23'11.5 W"),
    "k_0.jpg": ("Sirmilik National Park, Canada", "72°05'01.1 N 76°48'42.9 W"),
    "k_1.jpg": ("Golmud, China", "35°36'46.3 N 95°03'45.9 E"),
    "l_0.jpg": ("Nusantara, Indonesia", "0°58'18.1 S 116°41'58.9 E"),
    "l_1.jpg": ("Xinjiang, China", "40°04'02.8 N 77°40'00.7 E"),
    "l_2.jpg": ("Regina, Saskatchewan, Canada", "50°11'51.7 N 104°17'15.4 W"),
    "l_3.jpg": ("Regina, Saskatchewan, Canada", "50°12'41.3 N 104°43'38.1 W"),
    "m_0.jpg": ("Shenandoah River, Virginia", "38°46'32.2 N 78°24'07.1 W"),
    "m_1.jpg": ("Potomac River", "38°46'32.2 N 78°24'07.1 W"),
    "m_2.jpg": ("Tian Shan Mountains, Kyrgyzstan", "42°07'16.4 N 80°02'44.1 E"),
    "n_0.jpg": ("Yapacani, Bolivia", "17°18'29.7 S 63°53'19.0 W"),
    "n_1.jpg": ("Yapacani, Bolivia", "17°18'29.7 S 63°53'19.0 W"),
    "n_2.jpg": ("São Miguel do Araguaia, Brazil", "12°56'44.3 S 50°29'42.0 W"),
    "o_0.jpg": ("Crater Lake, Oregon", "42°56'10.0 N 122°06'04.7 W"),
    "o_1.jpg": ("Manicouagan Reservoir", "51°22'42.4 N 68°40'27.2 W"),
    "p_0.jpg": ("Mackenzie River Delta, Canada", "68°12'54.4 N 134°23'15.3 W"),
    "p_1.jpg": ("Riberalta, Bolivia", "10°52'44.0 S 66°02'52.0 W"),
    "q_0.jpg": ("Lonar Crater, India", "19°58'36.8 N 76°30'30.6 E"),
    "q_1.jpg": ("Mount Tambora, Indonesia", "8°14'31.3 S 117°59'31.2 E"),
    "r_0.jpg": ("Lago Menendez, Argentina", "42°41'14.9 S 71°52'21.7 W"),
    "r_1.jpg": ("Province of Sondrio, Italy", "46°17'38.3 N 9°25'14.5 E"),
    "r_2.jpg": ("Florida Keys", "24°45'30.4 N 81°31'53.6 W"),
    "r_3.jpg": ("Canyonlands National Park, Utah", "38°26'27.8 N 109°45'03.3 W"),
    "s_0.jpg": ("Mackenzie River", "68°25'01.0 N 134°08'35.2 W"),
    "s_1.jpg": ("N'Djamena, Chad", "12°00'27.7 N 15°03'46.2 E"),
    "s_2.jpg": ("Rio Chapare, Bolivia", "16°56'04.7 S 65°13'44.2 W"),
    "t_0.jpg": ("Liwa, United Arab Emirates", "23°10'30.0 N 53°47'52.8 E"),
    "t_1.jpg": ("Lena River Delta", "72°52'40.3 N 129°31'51.5 E"),
    "u_0.jpg": ("Canyonlands National Park, Utah", "38°16'09.1 N 109°55'32.7 W"),
    "u_1.jpg": ("Bamforth National Wildlife Refuge, Wyoming", "41°19'26.0 N 105°46'13.9 W"),
    "u_2.jpg": ("Potomac River, Virginia", "38°29'06.4 N 77°10'19.9 W"),
    "v_0.jpg": ("Cellina and Meduna Rivers, Italy", "46°06'41.4 N 12°45'26.6 E"),
    "v_1.jpg": ("New South Wales, Australia", "34°17'11.2 S 150°49'32.4 E"),
    "v_2.jpg": ("Padma River, Bangladesh", "23°21'03.9 N 90°33'06.9 E"),
    "v_3.jpg": ("Mapleton, Maine", "46°32'40.5 N 68°15'06.4 W"),
    "w_0.jpg": ("Ponoy River, Russia", "67°02'10.9 N 40°20'19.3 E"),
    "w_1.jpg": ("La Primavera, Columbia", "5°26'57.9 N 69°47'57.0 W"),
    "x_0.jpg": ("Wolstenholme Fjord, Greenland", "76°44'03.8 N 68°36'23.3 W"),
    "x_1.jpg": ("Davis Straight, Greenland", "62°14'14.8 N 49°34'49.9 W"),
    "x_2.jpg": ("Sermersooq Municipality, Greenland", "66°37'05.2 N 36°22'05.9 W"),
    "y_0.jpg": ("Bíobío River, Chile", "37°16'02.4 S 72°43'42.9 W"),
    "y_1.jpg": ("Estuario de Virrila, Peru", "5°51'53.4 S 80°43'51.6 W"),
    "y_2.jpg": ("Ramsay, New Zealand", "43°31'19.4 S 170°49'53.7 E"),
    "z_0.jpg": ("Primavera do Leste, Brazil", "15°29'38.9 S 54°20'27.5 W"),
    "z_1.jpg": ("Mohammed Boudiaf, Algeria", "34°59'19.3 N 4°23'20.8 E"),
}

LOCATIONS_PATH = Path(__file__).parent / "locations.json"

def write_locations():
    """Write locations data to JSON for frontend consumption."""
    data = {}
    for key, (title, coords) in LOCATIONS.items():
        data[key] = {"title": title, "coords": coords}
    LOCATIONS_PATH.write_text(json.dumps(data, indent=2))

if __name__ == "__main__":
    write_locations()
    print(f"Written {len(LOCATIONS)} entries to {LOCATIONS_PATH}")
