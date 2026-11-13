"""Lower Volga / North Caspian Neolithic-Eneolithic dates -> rows for
data/settlements/literature_dates.csv.

Sources (all open; text extracted with pdftotext -layout):
  V13  Vybornov, Kulkova, Goslar & Possnert 2013, Documenta Praehistorica 40:13-20, Tab. 1 (p. 16) + text
  V16  Vybornov 2016, Documenta Praehistorica 43:161-166, Tab. 1 (p. 164), Fig. 1 (p. 162)
  V17  Vybornov, Kulkova, Andreev & Nesterov 2017, Documenta Praehistorica 44:224-239, Tab. 1 (pp. 226-227)
  G14  Grechkina, Vybornov & Kutukov 2014, Samarskii nauchnyi vestnik 3(8), from p. 79 (Baibek location)
  V22  Vybornov, Giljazov, Doga, Kulkova & Philippsen 2022, Vestnik VolGU ser. 4, 27(3):6-15, Tab. 1 (pp. 9-10)
  B14  Burataev 2014, Vestnik KIGI RAN 2014(2): Dzhangar settlement 8.5 km from Dzhangar village
  S22  Vybornov, Vasilyeva, Laktaeva & Frolov 2022, Samarskii nauchnyi vestnik 11(4): Kairshak tract 25-30 km
       from pos. Aksaraysky, Krasnoyarsky district (p. 162)

Usage: python lower_volga.py <current literature_dates.csv> <out rows.csv>
Rows whose lab number is already in the current file are skipped.
"""
import csv
import re
import sys

import numpy as np

key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
COLS = "labnr,bp,std,lon,lat,site,type,period,material,approximate,precision,source,page,refs".split(",")

R13 = ("Vybornov, A., Kulkova, M., Goslar, T. & Possnert, G. 2013, The problem of the neolithisation process "
       "chronology in Povolzhye, Documenta Praehistorica 40:13-20, doi:10.4312/dp.40.2, "
       "https://journals.uni-lj.si/DocumentaPraehistorica/article/view/40.2 "
       "(PDF https://journals.uni-lj.si/DocumentaPraehistorica/article/download/40.2/794)")
R16 = ("Vybornov, A. 2016, Initial stages of two Neolithisation models in the Lower Volga basin, "
       "Documenta Praehistorica 43:161-166, doi:10.4312/dp.43.7, "
       "https://dlib.si/details/URN:NBN:SI:DOC-OZXW1NUW "
       "(PDF https://dlib.si/stream/URN:NBN:SI:DOC-OZXW1NUW/bec5d77d-c3fa-4b34-8970-ee9120ecbc2d/PDF)")
R17 = ("Vybornov, A., Kulkova, M., Andreev, K. & Nesterov, E. 2017, Radiocarbon chronology of the Neolithic "
       "in the Povolzhye (Russian Eastern Europe), Documenta Praehistorica 44:224-239, doi:10.4312/dp.44.14, "
       "https://journals.uni-lj.si/DocumentaPraehistorica/article/view/44.14 "
       "(PDF https://journals.uni-lj.si/DocumentaPraehistorica/article/download/44.14/7348)")
R22 = ("Vybornov, A.A., Giljazov, F.F., Doga, N.S., Kulkova, M.A. & Philippsen, B. 2022, The chronology of "
       "Neolithic-Eneolithic in the steppe zone of the Volga basin, Vestnik Volgogradskogo gosudarstvennogo "
       "universiteta, ser. 4, 27(3):6-15, doi:10.15688/jvolsu4.2022.3.1, "
       "https://hfrir.jvolsu.com/index.php/en/component/attachments/download/2820")
S13, S16, S17, S22 = ("Vybornov et al. 2013", "Vybornov 2016", "Vybornov et al. 2017", "Vybornov et al. 2022")

G14 = ("Grechkina, Vybornov & Kutukov 2014 (Samarskii nauchnyi vestnik 3(8):79ff, "
       "https://snv63.ru/2309-4370/article/download/22443/18625): 'sand massifs 11 km north of pos. Baibek, "
       "Krasnoyarsky district, Astrakhan oblast, on the Kigach'")
KAIR = ("approximate: Vybornov et al. 2022 (Samarskii nauchnyi vestnik 11(4):158ff, p. 162, "
        "https://snv63.ru/2309-4370/article/download/133233/111035) put the Kairshak tract 25-30 km from "
        "pos. Aksaraysky (OSM 46.793 N, 48.021 E) in Krasnoyarsky district, direction not given; "
        "placed at the existing XRONOS point for Kairsak III (46.7565 N, 47.9164 E), 9 km from Aksaraysky and "
        "consistent with the dot on Vybornov 2016 Fig. 1; Dolbunova et al. 2023's 47.42 N, 47.76 E is 72 km "
        "from Aksaraysky in Kharabalinsky district and is not used; about +-30 km")

# Georeference Vybornov 2016 Fig. 1 (the embedded 1260x1240 image): pixel -> lon, lat by an
# affine least-squares fit to four city dots and the Baibek site (fit residuals 5-12 km).
CTL = {"Astrakhan": ((778.75, 1167.5), (48.040, 46.349)), "Volgograd": ((591, 997), (44.516, 48.708)),
       "Saratov": ((664, 797), (46.034, 51.533)), "Samara": ((850, 658), (50.150, 53.195)),
       "Baibek": ((789.25, 1141.25), (48.458, 46.751))}
X = np.array([[p[0], p[1], 1] for p, _ in CTL.values()])
C = np.linalg.lstsq(X, np.array([g for _, g in CTL.values()]), rcond=None)[0]
DOTS = {"Kugat IV": (1, 755, 1097.5), "Kulagaysi": (2, 758, 1107), "Tenteksor I": (5, 776.25, 1111.75),
        "Karakhuduk": (8, 731.25, 1086.25), "Kurpezhe-Molla": (10, 770.5, 1121.25)}


def fig1(site):
    n, x, y = DOTS[site]
    lon, lat = np.array([x, y, 1]) @ C
    return (round(float(lon), 3), round(float(lat), 3), "site",
            f"approximate: Vybornov 2016 Fig. 1 (p. 162) locality {n} ({site}); "
            "read off the small-scale map georeferenced by an affine fit to Astrakhan, Volgograd, Saratov, Samara and "
            "the Baibek site (residuals 5-12 km); about +-20 km")


SITES = {
    "Kairshak III": (47.9164, 46.7565, "site", KAIR),
    "Kairshak I": (47.9164, 46.7565, "site", KAIR + "; Kairshak I is in the same tract (Vybornov et al. 2022, Samarskii nauchnyi vestnik, p. 162)"),
    "Kairshak VI": (47.9164, 46.7565, "site", KAIR + "; Kairshak VI assumed to be in the same tract"),
    "Baibek": (48.458, 46.751, "site",
               "approximate: " + G14 + "; placed 11 km due north of Baibek village (OSM 46.652 N, 48.458 E), "
               "which puts the Kigach 10 km to the south as the paper says; about +-3 km (Dolbunova et al. 2023's "
               "46.45 N, 48.84 E is 37 km away in Kazakhstan and is not used)"),
    "Jangar": (45.758, 47.657, "settlement",
               "approximate: Burataev, E.G. 2014, K istorii izucheniya poseleniya Dzhangar, Vestnik Kalmytskogo instituta gumanitarnykh issledovanii RAN 2014(2) (https://kigiran.elpub.ru/jour/article/download/1037/2075) "
               "puts the Dzhangar settlement on the north shore of liman Tankha 8.5 km from Dzhangar village, "
               "Oktyabrsky district, Kalmykia; placed at the village (OSM 47.657 N, 45.758 E), about +-10 km "
               "(the XRONOS 'Dzangar' point 47.946 N, 45.090 E is 59 km from the village)"),
    "Orlovka": (44.533, 48.847, "site",
                "approximate: Vybornov et al. 2017 Fig. 1 (p. 225) locality 8, just NW of Volgograd; placed at Orlovka "
                "village, Gorodishchensky district, Volgograd oblast (OSM 48.847 N, 44.533 E); the site is not located "
                "in the text, so about +-20 km"),
    "Varfolomeevskaya": (48.189, 50.012, "site",
                         "approximate: Maly Uzen by Varfolomeevka village, Aleksandrovo-Gaysky district, Saratov oblast; "
                         "placed at the village (50.012 N, 48.189 E), the point used for the XRONOS record in "
                         "data/settlements/corrections.toml; Vybornov 2016 Fig. 1 locality 6 georeferences to within 6 km; "
                         "about +-5 km"),
    "Algay": (48.53, 50.16, "site",
              "approximate: right bank of the Bolshoy Uzen, Alexandrovsky district, Saratov oblast; point from Dolbunova "
              "et al. 2023 SI_ORA site table (Algay 48.53, 50.16), as for the Kulkova et al. 2019 rows; it coincides "
              "with the district centre Aleksandrov Gay, about +-20 km"),
    "Oroshaemoe I": (48.53, 50.16, "settlement",
                     "approximate: right bank of the Bolshoy Uzen beside Algay (Kulkova et al. 2019 Fig. 1); placed at the "
                     "Algay point from Dolbunova et al. 2023 SI_ORA (48.53, 50.16), as for the Kulkova et al. 2019 rows; "
                     "about +-20 km"),
}
for s in DOTS:
    SITES[s] = fig1(s)

KT = "Neolithic, Kairshak type (North Caspian)"
TT = "Late Neolithic, Tenteksor type (North Caspian)"
JG = "Neolithic, Jangar culture (NW Caspian)"
OR = "Neolithic, Orlovka culture (Lower Volga steppe)"
KH = "Eneolithic, Khvalynsk culture (North Caspian)"
CC = "Early Eneolithic, Cis-Caspian (Prikaspiiskaya) culture"
RES = "; food crust/pottery carbon or fish/bone of riverine diet may carry a freshwater reservoir offset"

# (lab, bp, sd, site, period, material, source, page, ref)
D = [
    # Vybornov et al. 2017, Tab. 1 (lower Volga and Caspian part, nos. 1-43)
    ("Ua-41359", 7775, 42, "Kairshak III", KT, "food crust", S17, "p. 226, Tab. 1, no. 1 (also Vybornov et al. 2013 Tab. 1 no. 7)"),
    ("SPb-377", 7700, 100, "Kairshak III", KT, "food crust", S17, "p. 226, Tab. 1, no. 2 (Vybornov et al. 2013 Tab. 1 no. 8 prints 7700+-120)"),
    ("SPb-422", 7300, 100, "Kairshak III", KT, "pottery carbon", S17, "p. 226, Tab. 1, no. 3"),
    ("Ki-14633", 7190, 80, "Kairshak III", KT + "; upper layer, kulan bone, possibly early Tenteksor (Vybornov et al. 2013 p. 15)", "animal bone", S17, "p. 226, Tab. 1, no. 4 (also Vybornov et al. 2013 Tab. 1 no. 9, Vybornov 2016 Tab. 1)"),
    # no. 5 Ki-16401 (carbonates from pottery) and no. 6 'Ki-1600' (lab number misprinted) left out
    ("Ua-50262", 7937, 48, "Baibek", KT, "food crust", S17, "p. 226, Tab. 1, no. 7"),
    ("SPb-1712", 6827, 100, "Baibek", KT, "charcoal", S17, "p. 226, Tab. 1, no. 8"),
    ("Poz-57060", 7350, 50, "Baibek", KT, "food crust", S17, "p. 226, Tab. 1, no. 9 (also Grechkina et al. 2014)"),
    ("SPb-973", 6955, 80, "Baibek", KT, "animal bone", S16, "p. 164, Tab. 1 (also Grechkina et al. 2014; Vybornov et al. 2017 Tab. 1 no. 10 prints the same date as SPb-1709)"),
    ("SPb-1713", 6948, 120, "Baibek", KT, "charcoal", S17, "p. 226, Tab. 1, no. 11"),
    ("Ua-50260", 6986, 44, "Baibek", KT, "charcoal", S17, "p. 226, Tab. 1, no. 12 (also Vybornov 2016 Tab. 1)"),
    ("SPb-1716", 6925, 120, "Baibek", KT, "pottery carbon", S17, "p. 226, Tab. 1, no. 13 (Vybornov 2016 Tab. 1 prints 6920+-120 pottery carbon as SPb-1053, probably the same date)"),
    ("Ua-35227", 6695, 40, "Tenteksor I", TT, "pottery carbon (organics in shell-tempered pottery)", S13, "p. 14 text (lab no. as in the text; Vybornov et al. 2013 Tab. 1 no. 18 prints Ua 35 267, Vybornov 2016/Vybornov et al. 2017 Tab. 1 no. 14 print Ua-35277)"),
    ("SPb-315a", 6540, 100, "Tenteksor I", TT, "animal bone", S17, "p. 226, Tab. 1, no. 15 (also Vybornov et al. 2013 Tab. 1 no. 21)"),
    ("Ki-14101", 6640, 80, "Tenteksor I", TT, "pottery carbon", S17, "p. 226, Tab. 1, no. 16 (also Vybornov et al. 2013 Tab. 1 no. 19)"),
    ("SPb-423", 6650, 100, "Tenteksor I", TT, "pottery carbon", S17, "p. 226, Tab. 1, no. 17 (also Vybornov et al. 2013 Tab. 1 no. 20)"),
    ("Ki-14501", 7680, 100, "Kugat IV", KT, "pottery carbon", S17, "p. 226, Tab. 1, no. 18 (also Vybornov 2016 Tab. 1)"),
    ("Ki-14500", 7560, 90, "Kugat IV", KT, "pottery carbon", S17, "p. 226, Tab. 1, no. 19 (also Vybornov 2016 Tab. 1)"),
    ("SPb-1725", 7380, 120, "Kulagaysi", KT, "pottery carbon", S17, "p. 226, Tab. 1, no. 20 (also Vybornov 2016 Tab. 1)"),
    ("Ki-14639", 7080, 90, "Jangar", JG + "; layer 3", "pottery carbon", S17, "p. 226, Tab. 1, no. 21"),
    ("Ki-14640", 6990, 90, "Jangar", JG + "; layer 3", "pottery carbon", S17, "p. 226, Tab. 1, no. 22"),
    ("IGAN-2819", 6870, 130, "Jangar", JG + "; layer 2-3", "charcoal", S17, "p. 226, Tab. 1, no. 23"),
    ("Le-2564", 6100, 70, "Jangar", JG + "; layer 2", "charcoal", S17, "p. 226, Tab. 1, no. 24"),
    ("Ki-14641", 6780, 90, "Jangar", JG + "; layer 2", "pottery carbon", S17, "p. 226, Tab. 1, no. 25"),
    ("Le-2901", 5890, 70, "Jangar", JG + "; layer 1", "charcoal", S17, "p. 226, Tab. 1, no. 26"),
    ("Hela-3255", 6564, 44, "Jangar", JG + "; layer 1", "food crust", S17, "p. 226, Tab. 1, no. 27"),
    ("GIN-6546", 6980, 200, "Varfolomeevskaya", OR + "; layer 3", "charcoal", S17, "p. 226, Tab. 1, no. 28"),
    ("Ki-14109", 7250, 80, "Varfolomeevskaya", OR + "; layer 3", "pottery carbon", S17, "p. 226, Tab. 1, no. 29"),
    ("SPb-941", 7100, 110, "Varfolomeevskaya", OR + "; layer 2B", "food crust", S17, "p. 226, Tab. 1, no. 31"),
    ("Ua-41360", 7034, 41, "Varfolomeevskaya", OR + "; layer 2B", "food crust", S17, "p. 226, Tab. 1, no. 32 (also Vybornov 2016 Tab. 1)"),
    ("Poz-52697", 6850, 40, "Varfolomeevskaya", OR + "; layer 2B", "food crust", S17, "p. 226, Tab. 1, no. 33"),
    ("SPb-1727", 6647, 150, "Orlovka", OR, "pottery carbon", S17, "p. 226, Tab. 1, no. 37"),
    ("Ua-41361", 6544, 38, "Varfolomeevskaya", OR + "; layer 2A", "food crust", S17, "p. 226, Tab. 1, no. 38 (also Vybornov et al. 2013 Tab. 1 no. 24)"),
    ("SPb-937", 6363, 150, "Varfolomeevskaya", OR + "; layer 2A", "food crust", S17, "p. 226, Tab. 1, no. 40"),
    ("SPb-939", 5800, 150, "Varfolomeevskaya", "Orlovka culture pottery from the upper layer (Vybornov et al. 2022 p. 12); 'Varfolomeevskaya (upper)' in Vybornov et al. 2017", "food crust", S17, "p. 226, Tab. 1, no. 41 (also Vybornov et al. 2022 p. 12)"),
    ("Ki-14614", 5870, 90, "Varfolomeevskaya", "Eneolithic (no layer given)", "pottery carbon", S17, "p. 226, Tab. 1, no. 43"),
    # Vybornov et al. 2013, Tab. 1 (p. 16), dates not in Vybornov et al. 2017
    ("GIN-5905", 6950, 190, "Kairshak III", KT, "humic acids", S13, "p. 16, Tab. 1, no. 1"),
    ("GIN-5927", 6720, 80, "Kairshak III", KT, "humic acids", S13, "p. 16, Tab. 1, no. 2"),
    ("Ki-14097", 7890, 90, "Kairshak III", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 3"),
    ("Ki-14471", 7780, 90, "Kairshak III", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 4"),
    ("Ki-14095", 7740, 70, "Kairshak III", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 5"),
    ("Ki-14096", 7680, 90, "Kairshak III", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 6"),
    ("Ki-14634", 7010, 80, "Kairshak III", KT + "; upper layer, kulan bone, possibly early Tenteksor (p. 15)", "animal bone", S13, "p. 16, Tab. 1, no. 10"),
    ("SPb-316", 7030, 100, "Kairshak III", KT + "; kulan bone, possibly early Tenteksor (p. 15)", "animal bone", S13, "p. 16, Tab. 1, no. 11"),
    ("Ki-14094", 7230, 90, "Kairshak I", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 12"),
    ("Ki-14132", 7180, 90, "Kairshak I", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 13 (text p. 15 prints 7180+-80)"),
    ("SPb-425", 7100, 200, "Kairshak I", KT, "pottery carbon", S13, "p. 16, Tab. 1, no. 14"),
    ("GIN-6177", 5500, 150, "Tenteksor I", TT + "; humic acids from soil, the authors take it as a later burning event", "humic acids", S13, "p. 16, Tab. 1, no. 15"),
    ("SPb-315", 5560, 100, "Tenteksor I", TT + "; burnt bone, the authors take it as a later burning event", "burnt bone", S13, "p. 16, Tab. 1, no. 16"),
    ("Le-9476", 6070, 290, "Tenteksor I", TT, "animal bone", S13, "p. 16, Tab. 1, no. 22"),
    # no. 17 Ua-35226 (shells from pottery) left out
    ("Ua-41362", 6693, 39, "Varfolomeevskaya", OR + "; layer 2A", "food crust", S13, "p. 16, Tab. 1, no. 23"),
    ("Ki-14613", 6540, 80, "Varfolomeevskaya", OR + "; layer 2A", "pottery carbon", S13, "p. 16, Tab. 1, no. 25"),
    ("Ki-3589", 5430, 60, "Varfolomeevskaya", OR + "; layer 2A", "animal bone", S13, "p. 16, Tab. 1, no. 26"),
    ("Ki-3595", 5390, 60, "Varfolomeevskaya", OR + "; layer 2A", "animal bone", S13, "p. 16, Tab. 1, no. 27"),
    ("Ki-3590", 5270, 50, "Varfolomeevskaya", OR + "; layer 2A", "animal bone", S13, "p. 16, Tab. 1, no. 28"),
    ("Ki-3596", 5220, 50, "Varfolomeevskaya", OR + "; layer 2A", "animal bone", S13, "p. 16, Tab. 1, no. 29"),
    # Vybornov 2016, Tab. 1 (p. 164), dates not in Vybornov et al. 2013/Vybornov et al. 2017
    ("Ki-14368", 7230, 90, "Varfolomeevskaya", OR, "pottery carbon", S16, "p. 164, Tab. 1"),
    ("Ki-14907", 5980, 90, "Karakhuduk", KH, "pottery carbon", S16, "p. 164, Tab. 1"),
    ("Ki-14910", 5780, 90, "Kairshak VI", KH, "pottery carbon", S16, "p. 164, Tab. 1"),
    ("Ki-14832", 6020, 80, "Kurpezhe-Molla", CC, "pottery carbon", S16, "p. 164, Tab. 1"),
    # Burovaya 41 (Ki-14618) left out: not located in the paper
    # Vybornov et al. 2022, Tab. 1 (pp. 9-10): Algay and Oroshaemoe I dates not already in the file
    ("AAR-21894", 7580, 46, "Algay", "Neolithic, Orlovka culture (lower layer)", "fish vertebrae", S22, "p. 9, Tab. 1, no. 1"),
    ("SPb-3347", 7263, 100, "Algay", "Neolithic-Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 3"),
    ("SPb-3115", 7145, 100, "Algay", "Neolithic-Eneolithic (level 30)", "bone", S22, "p. 9, Tab. 1, no. 4"),
    ("SPb-3346", 6882, 100, "Algay", "Neolithic-Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 5"),
    # no. 10 SPb-1778 6577+-80 is the date printed as SPb-1478 by Kulkova et al. 2019 and V17, already in the file
    ("SPb-2726", 6540, 110, "Algay", "Neolithic, Orlovka culture (middle-late stage)", "pottery", S22, "p. 9, Tab. 1, no. 11"),
    ("SPb-3360", 6200, 70, "Algay", "Neolithic-Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 18"),
    ("SPb-3348", 6205, 120, "Algay", "Neolithic-Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 19"),
    ("SPb-3345", 5955, 60, "Algay", "Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 20"),
    ("SPb-3359", 5875, 60, "Algay", "Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 21"),
    ("SPb-1475", 5720, 120, "Algay", "Eneolithic (50-60 cm)", "bone", S22, "p. 9, Tab. 1, no. 23"),
    ("SPb-3116", 5846, 70, "Algay", "Eneolithic (layer not given)", "bone", S22, "p. 9, Tab. 1, no. 24"),
    ("SPb-1476", 5680, 80, "Algay", "Eneolithic (60-70 cm)", "bone", S22, "p. 9, Tab. 1, no. 25"),
    ("SPb-2090", 6889, 100, "Oroshaemoe I", "Neolithic, Orlovka culture (level 22-23)", "bone", S22, "p. 9, Tab. 1, no. 28"),
    ("SPb-2854", 6620, 100, "Oroshaemoe I", "Neolithic (level 40)", "charcoal", S22, "p. 10, Tab. 1, no. 29"),
    ("SPb-2853", 6580, 100, "Oroshaemoe I", "Neolithic (level 39)", "charcoal", S22, "p. 10, Tab. 1, no. 30"),
    ("Hela-4005", 6551, 40, "Oroshaemoe I", "Neolithic (level 31)", "charcoal", S22, "p. 10, Tab. 1, no. 31"),
    ("SPb-1729", 5890, 120, "Oroshaemoe I", CC, "pottery", S22, "p. 10, Tab. 1, no. 33"),
    ("SPb-2471", 5716, 110, "Oroshaemoe I", "Eneolithic (150 cm)", "humic acids", S22, "p. 10, Tab. 1, no. 35"),
    ("SPb-2634", 5520, 90, "Oroshaemoe I", "Eneolithic", "humic acids", S22, "p. 10, Tab. 1, no. 36"),
    ("SPb-1474", 5667, 100, "Oroshaemoe I", "Eneolithic", "bone", S22, "p. 10, Tab. 1, no. 37"),
    ("AAR-26176", 5328, 33, "Oroshaemoe I", "Eneolithic", "food crust", S22, "p. 10, Tab. 1, no. 38"),
]
REF = {S13: R13, S16: R16, S17: R17, S22: R22}
RISKY = ("food crust", "pottery", "fish")

have = {key(r["labnr"]) for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))}
out, skipped = [], []
for lab, bp, sd, site, period, mat, src, page in D:
    if key(lab) in have or key(lab) in {key(r["labnr"]) for r in out}:
        skipped.append(lab)
        continue
    lon, lat, typ, prec = SITES[site]
    if any(m in mat for m in RISKY):
        period += RES
    out.append(dict(labnr=lab, bp=bp, std=sd, lon=lon, lat=lat, site=site, type=typ, period=period,
                    material=mat, approximate="true", precision=prec, source=src, page=page, refs=REF[src]))
with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, COLS)
    w.writeheader()
    w.writerows(out)
print(len(out), "rows,", len({r["site"] for r in out}), "sites; skipped (already in file):", skipped)
for s in sorted({r["site"] for r in out}):
    print(" ", s, SITES[s][:2])
