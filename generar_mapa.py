import geopandas as gpd
import folium
from folium import Element
import warnings
import pandas as pd
import json
import base64
import os

# ─── CARGAR IMÁGENES COMO BASE64 PARA EMBEBER EN EL HTML ───────────────────────
def img_b64(filename):
    path = os.path.join("assets", filename)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

print("Codificando imágenes en base64...")
IMGS = {
    "bosque_niebla":   img_b64("bosque_niebla.png"),
    "orquidea":        img_b64("orquidea.png"),
    "helecho":         img_b64("helecho.png"),
    "clarin_jilguero": img_b64("clarin_jilguero.png"),
    "tlacuache":       img_b64("tlacuache.png"),
    "cafetal":         img_b64("cafetal.png"),
}

# Carruseles por tipo de ecosistema
CAROUSEL_DATA = {
    "bosque": [
        {"src": "bosque_niebla",   "label": "Bosque de Niebla",         "tipo": "Ecosistema"},
        {"src": "orquidea",        "label": "Laelia anceps",            "tipo": "Flora · Orquídea Epífita"},
        {"src": "helecho",         "label": "Cyathea spp.",             "tipo": "Flora · Helecho Arborescente"},
        {"src": "clarin_jilguero", "label": "Myadestes occidentalis",   "tipo": "Fauna · Clarín Jilguero"},
        {"src": "tlacuache",       "label": "Philander opossum",        "tipo": "Fauna · Tlacuache"},
    ],
    "cafe": [
        {"src": "cafetal",         "label": "Cafetal bajo Sombra",      "tipo": "Agroforestal · Paisaje"},
        {"src": "orquidea",        "label": "Laelia anceps",            "tipo": "Flora · Orquídea Epífita"},
        {"src": "clarin_jilguero", "label": "Myadestes occidentalis",   "tipo": "Fauna · Clarín Jilguero"},
        {"src": "tlacuache",       "label": "Philander opossum",        "tipo": "Fauna · Tlacuache"},
    ],
    "pastizal": [
        {"src": "bosque_niebla",   "label": "Bosque de Niebla",         "tipo": "Ecosistema colindante"},
        {"src": "tlacuache",       "label": "Philander opossum",        "tipo": "Fauna · Tlacuache"},
        {"src": "clarin_jilguero", "label": "Myadestes occidentalis",   "tipo": "Fauna · Clarín Jilguero"},
    ],
    "urbano": [
        {"src": "bosque_niebla",   "label": "Bosque de Niebla",         "tipo": "Ecosistema amenazado"},
        {"src": "orquidea",        "label": "Laelia anceps",            "tipo": "Flora · Orquídea Epífita"},
        {"src": "tlacuache",       "label": "Philander opossum",        "tipo": "Fauna · Tlacuache"},
    ],
}

# ─── COLOR POR USO DE SUELO ────────────────────────────────────────────────────
def color_uso_suelo(desc):
    desc = str(desc).upper()
    if 'ASENTAMIENTOS' in desc or 'URBANO' in desc:
        return '#9ca3af'
    elif 'AGUA' in desc:
        return '#3b82f6'
    elif 'BOSQUE' in desc and 'SECUNDARIA' not in desc:
        return '#059669'
    elif 'SELVA' in desc and 'SECUNDARIA' not in desc:
        return '#16a34a'
    elif 'AGRICULTURA' in desc:
        return '#d97706'
    elif 'PASTIZAL' in desc:
        return '#84cc16'
    elif 'SECUNDARIA' in desc or 'VEGETAC' in desc:
        return '#65a30d'
    return '#57534e'

# ─── CARGA DE SHAPEFILES ──────────────────────────────────────────────────────
print("Cargando archivos Shapefile...")
anp       = gpd.read_file("ANP Archipielago.shp",    encoding='latin1')
uso_suelo = gpd.read_file("Uso_de_sueloANPABYS.shp", encoding='latin1')
rios      = gpd.read_file("Rios.shp",                encoding='latin1')

municipios_nombres = ["Xalapa", "Coatepec", "Emiliano_Zapata", "Banderilla", "Tlalnelhuayocan"]
mun_gdfs = []
for nombre in municipios_nombres:
    g = gpd.read_file(f"{nombre}.shp", encoding='latin1')
    g['Nombre_Municipio'] = nombre.replace("_", " ")
    mun_gdfs.append(g[['Nombre_Municipio', 'geometry']])
municipios = pd.concat(mun_gdfs, ignore_index=True)

# ─── SIMPLIFICACIÓN GEOMÉTRICA ────────────────────────────────────────────────
print("Simplificando geometrías...")
rios_simp      = rios.copy();      rios_simp.geometry      = rios.geometry.simplify(15, preserve_topology=True)
uso_suelo_simp = uso_suelo.copy(); uso_suelo_simp.geometry = uso_suelo.geometry.simplify(10, preserve_topology=True)

# ─── INTERSECCIÓN ANP × MUNICIPIOS ───────────────────────────────────────────
print("Calculando intersección de fragmentos...")
anp_utm        = anp.to_crs(epsg=32614)
municipios_utm = municipios.to_crs(epsg=32614)
anp_utm.geometry        = anp_utm.geometry.buffer(0)
municipios_utm.geometry = municipios_utm.geometry.buffer(0)

anp_ind  = anp_utm.explode(index_parts=False).reset_index(drop=True)
anp_isec = gpd.overlay(anp_ind, municipios_utm, how='intersection').reset_index(drop=True)

anp_isec['Fragment_ID']        = [f"FRAG_{i+1:02d}" for i in range(len(anp_isec))]
anp_isec['Area_Hectareas_Num'] = (anp_isec.geometry.area / 10_000).round(2)
anp_isec['Area (Hectareas)']   = anp_isec['Area_Hectareas_Num'].astype(str) + " ha"

tmp = anp_isec.to_crs(epsg=4326)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    pts = tmp.geometry.representative_point()
    anp_isec['Coordenadas'] = pts.y.round(5).astype(str) + "°, " + pts.x.round(5).astype(str) + "°"
    anp_isec['lat_num'] = pts.y.round(5)
    anp_isec['lon_num'] = pts.x.round(5)

# ─── CRUCE CON USO DE SUELO + FICHA ECOLÓGICA ────────────────────────────────
print("Enriqueciendo fragmentos con uso de suelo y datos ecológicos...")
uso_utm = uso_suelo.to_crs(epsg=32614)
uso_utm.geometry = uso_utm.geometry.buffer(0)

eco_tipos = []; eco_descs = []; floras = []; faunas = []
usos_json = []; carousel_keys = []

for _, row in anp_isec.iterrows():
    geom = row['geometry']
    bbox = geom.bounds
    cands = uso_utm.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    composicion = {}
    if not cands.empty:
        try:
            frag_gdf = gpd.GeoDataFrame([row], crs=anp_isec.crs)
            inter    = gpd.overlay(frag_gdf, cands, how='intersection')
            if not inter.empty:
                inter['Area_ha'] = inter.geometry.area / 10_000
                st   = inter.groupby('DESCRIPCIO')['Area_ha'].sum().reset_index()
                tot  = st['Area_ha'].sum()
                if tot > 0:
                    st['Pct'] = (st['Area_ha'] / tot * 100).round(1)
                    composicion = st.set_index('DESCRIPCIO')['Pct'].to_dict()
        except Exception as e:
            print(f"  Advertencia en fragmento {row['Fragment_ID']}: {e}")

    usos_json.append(composicion)

    ab = bf = af = ap = au = 0.0
    for cat, pct in composicion.items():
        cu = cat.upper()
        if 'BOSQUE' in cu or 'SECUNDARIA' in cu or 'SELVA' in cu:
            ab += pct
        elif 'AGRICULTURA' in cu:
            af += pct
        elif 'PASTIZAL' in cu:
            ap += pct
        elif 'ASENTAMIENTOS' in cu or 'URBANO' in cu:
            au += pct

    if ab >= af and ab >= ap and ab >= au:
        eco_tipo = "Bosque Mesófilo de Montaña"
        eco_desc = ("Conserva relictos del Bosque de Niebla, el ecosistema con mayor biodiversidad "
                    "de México por unidad de área. Regula la humedad regional y capta agua de neblina "
                    "para abastecer a la región metropolitana de Xalapa.")
        flora  = "Liquidámbar (Liquidambar styraciflua),Helecho Arborescente (Cyathea),Orquídea Epífita (Laelia anceps),Encino (Quercus),Musgos y Briófitos"
        fauna  = "Clarín Jilguero (Myadestes occidentalis),Salamandra Endémica,Colibrí Cola de Hilo,Tlacuache de Cuatro Ojos,Ardilla de Peter"
        ckey   = "bosque"
    elif af >= ap and af >= au:
        eco_tipo = "Cafetal bajo Sombra (Agroforestal)"
        eco_desc = ("Sector con cultivo tradicional de café bajo sombra. Mantiene alta biodiversidad, "
                    "conecta áreas boscosas y permite la infiltración hídrica. Es el modelo productivo "
                    "más compatible con la conservación del Bosque de Niebla.")
        flora  = "Cafeto (Coffea arabica),Jinicuil / Inga (Inga vera),Banana Silvestre,Árbol de Sombra,Liquidámbar Residual"
        fauna  = "Ardilla Gris (Sciurus aureogaster),Carpintero Cheje,Tarántula Rodillas Rojas,Murciélago Frutero,Colibrí"
        ckey   = "cafe"
    elif ap >= au:
        eco_tipo = "Pastizal con Matorral Secundario"
        eco_desc = ("Área con pastizales cultivados en transición ecológica. Presenta parches "
                    "de matorral y vegetación arbustiva que propician la regeneración natural del bosque "
                    "si se reduce la presión ganadera.")
        flora  = "Pastos Introducidos,Acacia / Huizache,Capulín (Prunus serotina),Encino Arbustivo,Escobillo"
        fauna  = "Gavilán Rastrero,Conejo Floridano (Sylvilagus floridanus),Lagartija Espinosa,Cenzontle,Halconcillo Cernícalo"
        ckey   = "pastizal"
    else:
        eco_tipo = "Zona de Amortiguamiento Urbano"
        eco_desc = ("Sector expuesto al crecimiento urbano perimetral. Actúa como zona de amortiguamiento "
                    "crítico entre las ciudades y los núcleos boscosos del Archipiélago. "
                    "Su conservación es vital para mantener la conectividad del corredor biológico.")
        flora  = "Jacaranda Ornamental,Eucalipto,Pastos Ruderales,Ficus,Especies Exóticas"
        fauna  = "Cacomixtle (Bassariscus astutus),Gorrión Común,Tlacuache Común,Colibrí Pico Ancho,Lagartijas Urbanas"
        ckey   = "urbano"

    eco_tipos.append(eco_tipo)
    eco_descs.append(eco_desc)
    floras.append(flora)
    faunas.append(fauna)
    carousel_keys.append(ckey)

anp_isec['Eco_Tipo']     = eco_tipos
anp_isec['Eco_Desc']     = eco_descs
anp_isec['Flora']        = floras
anp_isec['Fauna']        = faunas
anp_isec['Carousel_Key'] = carousel_keys
anp_isec['Uso_JSON']     = [json.dumps(u) for u in usos_json]
anp_isec['Nombre_ANP']   = [f"Fragmento {r['Fragment_ID']}" for _, r in anp_isec.iterrows()]

# ─── PROYECCIÓN WGS84 ─────────────────────────────────────────────────────────
print("Proyectando a WGS84...")
anp_final        = anp_isec.to_crs(epsg=4326)
municipios_wgs84 = municipios_utm.to_crs(epsg=4326)
uso_suelo_wgs84  = uso_suelo_simp.to_crs(epsg=4326)
rios_wgs84       = rios_simp.to_crs(epsg=4326)

# ─── ESTADÍSTICAS GLOBALES ────────────────────────────────────────────────────
print("Calculando estadísticas globales...")
stats_mun = {k: round(v, 2) for k, v in anp_isec.groupby('Nombre_Municipio')['Area_Hectareas_Num'].sum().items()}
total_ha   = round(sum(stats_mun.values()), 2)

uso_anp    = gpd.overlay(uso_utm, anp_utm, how='intersection')
uso_anp['Area_ha'] = uso_anp.geometry.area / 10_000
global_uso = {'Bosques de Niebla': 0.0, 'Cafetales y Agrícola': 0.0,
              'Pastizales (Ganado)': 0.0, 'Zonas Urbanas': 0.0, 'Cuerpos de Agua': 0.0}
for k, v in uso_anp.groupby('DESCRIPCIO')['Area_ha'].sum().items():
    cat = k.upper(); val = round(float(v), 2)
    if 'BOSQUE' in cat or 'SECUNDARIA' in cat or 'SELVA' in cat:
        global_uso['Bosques de Niebla'] += val
    elif 'AGRICULTURA' in cat:
        global_uso['Cafetales y Agrícola'] += val
    elif 'PASTIZAL' in cat:
        global_uso['Pastizales (Ganado)'] += val
    elif 'ASENTAMIENTOS' in cat or 'URBANO' in cat:
        global_uso['Zonas Urbanas'] += val
    elif 'AGUA' in cat:
        global_uso['Cuerpos de Agua'] += val
global_uso = {k: round(v, 2) for k, v in global_uso.items()}

# ─── DATOS DEL CARRUSEL EN JSON (con imágenes b64) ──────────────────────────
carousel_json = {}
for key, slides in CAROUSEL_DATA.items():
    carousel_json[key] = [
        {"src": IMGS.get(s["src"], ""), "label": s["label"], "tipo": s["tipo"]}
        for s in slides
    ]

# ─── MAPA FOLIUM ─────────────────────────────────────────────────────────────
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    bounds   = anp_final.total_bounds
    centro_y = (bounds[1] + bounds[3]) / 2
    centro_x = (bounds[0] + bounds[2]) / 2

print("Inicializando mapa Folium...")
m = folium.Map(location=[centro_y, centro_x], tiles=None,
               control_scale=True, zoom_control=False)
m.fit_bounds([[bounds[1]-0.04, bounds[0]-0.04], [bounds[3]+0.04, bounds[2]+0.04]])

# ─── CAPAS (fondo → primer plano) ────────────────────────────────────────────
folium.GeoJson(uso_suelo_wgs84, name="Uso de Suelo", show=False,
    style_function=lambda f: {'fillColor': color_uso_suelo(f['properties']['DESCRIPCIO']),
                              'color': color_uso_suelo(f['properties']['DESCRIPCIO']),
                              'weight': 0.3, 'fillOpacity': 0.4},
    highlight_function=lambda f: {'fillOpacity': 0.65, 'weight': 1.0, 'color': '#fff'},
).add_to(m)

folium.GeoJson(rios_wgs84, name="Ríos", show=False,
    style_function=lambda f: {'color': '#38bdf8', 'weight': 1.0, 'opacity': 0.7},
    highlight_function=lambda f: {'color': '#7dd3fc', 'weight': 2.0, 'opacity': 1.0},
).add_to(m)

folium.GeoJson(municipios_wgs84, name="Municipios", show=True,
    style_function=lambda f: {'fillColor': 'transparent', 'color': 'rgba(96,165,250,0.6)',
                              'weight': 1.5, 'fillOpacity': 0, 'dashArray': '5 5'},
    highlight_function=lambda f: {'fillColor': 'rgba(59,130,246,0.05)', 'weight': 2.0, 'color': '#93c5fd'},
).add_to(m)

folium.GeoJson(anp_final, name="ANP Archipiélago", show=True,
    style_function=lambda f: {'fillColor': '#10b981', 'color': '#34d399', 'weight': 2.5, 'fillOpacity': 0.6},
    highlight_function=lambda f: {'fillColor': '#059669', 'fillOpacity': 0.75, 'weight': 3.5, 'color': '#a7f3d0'},
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ─── DASHBOARD HTML / CSS / JS ───────────────────────────────────────────────
DASHBOARD = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', sans-serif; overflow: hidden; background: #060b14; }

/* ── Scrollbar ────────────────────── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 2px; }

/* ── Hide Leaflet native controls ─── */
.leaflet-control-layers { display:none!important; }
.leaflet-bottom.leaflet-right { margin: 0 14px 14px 0; }
.leaflet-bar { border:1px solid rgba(255,255,255,0.08)!important; border-radius:10px!important;
    box-shadow:0 8px 24px rgba(0,0,0,0.6)!important; overflow:hidden; }
.leaflet-bar a { background:rgba(10,15,30,0.9)!important; backdrop-filter:blur(10px);
    color:#94a3b8!important; border-bottom:1px solid rgba(255,255,255,0.06)!important; transition:.2s; }
.leaflet-bar a:hover { background:#10b981!important; color:#fff!important; }
.leaflet-control-scale-line { background:rgba(10,15,30,0.8)!important; border-color:rgba(255,255,255,0.15)!important;
    color:#94a3b8!important; font-size:10px!important; padding:1px 6px!important; border-radius:4px!important; }

/* ── Glass Panel ──────────────────── */
.gp {
    background: rgba(10,16,30,0.72);
    backdrop-filter: blur(16px) saturate(180%);
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.07);
    box-shadow: 0 8px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06);
    color: #e2e8f0;
    border-radius: 14px;
}

/* ── Header ───────────────────────── */
.hdr {
    position: absolute; top: 10px; left: 10px; right: 10px; height: 66px;
    z-index: 1000; display: flex; align-items: center; justify-content: space-between;
    padding: 0 22px;
}
.hdr-left { display:flex; align-items:center; gap:14px; }
.hdr-icon {
    width:46px; height:46px; border-radius:11px; font-size:22px;
    display:flex; align-items:center; justify-content:center;
    background:linear-gradient(135deg, rgba(16,185,129,0.25), rgba(5,150,105,0.1));
    border:1px solid rgba(16,185,129,0.35);
    box-shadow:0 0 20px rgba(16,185,129,0.15), inset 0 1px 0 rgba(255,255,255,0.08);
}
.hdr-name { font-family:'Outfit',sans-serif; font-size:17px; font-weight:700; color:#f8fafc; letter-spacing:.2px; }
.hdr-sub  { font-size:10.5px; color:#10b981; font-weight:600; text-transform:uppercase; letter-spacing:.6px; margin-top:2px; }
.hdr-kpis { display:flex; gap:28px; }
.kpi { display:flex; flex-direction:column; align-items:flex-end; }
.kpi-lbl { font-size:9px; color:#475569; text-transform:uppercase; letter-spacing:.7px; }
.kpi-val { font-family:'Outfit',sans-serif; font-size:16px; font-weight:700; color:#f1f5f9; margin-top:1px; }
.kpi-val.green { color:#10b981; text-shadow:0 0 12px rgba(16,185,129,0.3); }

/* ── Sidebars ─────────────────────── */
.sb {
    position:absolute; top:88px; bottom:10px;
    width:310px; border-radius:14px; z-index:1000;
    padding:16px; display:flex; flex-direction:column; gap:14px;
    overflow-y:auto; overflow-x:hidden;
}
.sb-left  { left:10px; }
.sb-right { right:10px; }

/* ── Section Title ────────────────── */
.sec {
    font-size:9.5px; font-weight:700; color:#475569;
    text-transform:uppercase; letter-spacing:1.3px;
    padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.05);
    margin-bottom:4px;
}

/* ── Search ───────────────────────── */
.srch-wrap { position:relative; }
.srch-inp {
    width:100%; padding:10px 14px 10px 34px;
    background:rgba(0,0,0,0.35); border:1px solid rgba(255,255,255,0.08);
    border-radius:9px; color:#f1f5f9; font-size:12px; font-family:'Inter',sans-serif;
    outline:none; transition:.2s;
}
.srch-inp:focus { border-color:#10b981; box-shadow:0 0 0 2px rgba(16,185,129,0.1); }
.srch-ico { position:absolute; left:11px; top:11px; font-size:13px; color:#475569; pointer-events:none; }
.srch-dd {
    position:absolute; top:105%; left:0; right:0;
    background:rgba(12,18,32,0.97); backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,0.09); border-radius:10px;
    max-height:190px; overflow-y:auto; z-index:1002;
    display:none; box-shadow:0 12px 30px rgba(0,0,0,0.6);
}
.srch-item { padding:8px 14px; font-size:12px; color:#cbd5e1; cursor:pointer;
    border-bottom:1px solid rgba(255,255,255,0.03); transition:.15s; }
.srch-item:hover { background:rgba(16,185,129,0.12); color:#fff; }
.srch-empty { padding:8px 14px; font-size:12px; color:#475569; font-style:italic; cursor:default; }

/* ── Filters ──────────────────────── */
.ftrs { display:flex; flex-wrap:wrap; gap:5px; margin-top:5px; }
.ftr {
    padding:5px 9px; border-radius:6px; font-size:10.5px;
    background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.07);
    color:#94a3b8; cursor:pointer; transition:.18s;
}
.ftr:hover { background:rgba(255,255,255,0.08); color:#e2e8f0; }
.ftr.on { background:rgba(16,185,129,0.18); border-color:#10b981; color:#f0fdf4; font-weight:600; }

/* ── Layer Toggles ────────────────── */
.ltgs { display:flex; flex-direction:column; gap:5px; margin-top:4px; }
.ltg {
    display:flex; align-items:center; gap:10px; padding:8px 12px;
    background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05);
    border-radius:8px; cursor:pointer; font-size:12px; color:#cbd5e1;
    transition:.18s; user-select:none;
}
.ltg:hover { background:rgba(255,255,255,0.05); }
.ltg.off { opacity:.38; }
.chk {
    width:14px; height:14px; border-radius:4px; flex-shrink:0;
    border:1.5px solid rgba(255,255,255,0.25); position:relative; transition:.15s;
}
.chk.on { background:#10b981; border-color:#10b981; box-shadow:0 0 7px rgba(16,185,129,0.5); }
.chk.on::after { content:'✓'; position:absolute; top:-2px; left:2px; font-size:9px; font-weight:700; color:#fff; }
.ldot { width:9px; height:9px; border-radius:50%; margin-left:auto; flex-shrink:0; }

/* ── Basemaps ─────────────────────── */
.bms { display:flex; gap:5px; margin-top:5px; }
.bm {
    flex:1; padding:8px 4px; border-radius:7px; font-size:10.5px; text-align:center;
    background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07);
    color:#94a3b8; cursor:pointer; transition:.18s;
}
.bm:hover { background:rgba(255,255,255,0.07); color:#e2e8f0; }
.bm.on { background:rgba(14,165,233,0.18); border-color:rgba(14,165,233,0.6); color:#e0f2fe; font-weight:600; }

/* ── Charts ───────────────────────── */
.chart-box { position:relative; width:100%; height:115px; margin-top:5px; }

/* ── Right panel placeholder ──────── */
.placeholder {
    flex:1; display:flex; flex-direction:column; align-items:center;
    justify-content:center; text-align:center; color:#475569; padding:20px;
}
.ph-icon { font-size:40px; margin-bottom:14px; animation:ph-pulse 2.4s ease-in-out infinite; }
@keyframes ph-pulse { 0%,100%{transform:scale(1);opacity:.5} 50%{transform:scale(1.1);opacity:.8} }
.ph-txt { font-size:12px; line-height:1.65; }

/* ── Fragment Details ─────────────── */
.det { display:flex; flex-direction:column; gap:12px; animation:slide-in .35s cubic-bezier(.16,1,.3,1); }
@keyframes slide-in { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }

.det-hdr { display:flex; align-items:flex-start; gap:10px; padding-bottom:10px;
    border-bottom:1px solid rgba(255,255,255,0.06); }
.bid { font-family:monospace; font-size:10px; font-weight:700; padding:3px 7px; border-radius:5px;
    background:rgba(16,185,129,0.12); color:#10b981; border:1px solid rgba(16,185,129,0.25); white-space:nowrap; }
.det-title { font-family:'Outfit',sans-serif; font-size:15px; font-weight:700; color:#f8fafc; line-height:1.3; }
.det-mun   { font-size:10.5px; color:#64748b; margin-top:2px; }

.dgrid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.dcard { background:rgba(0,0,0,0.22); border:1px solid rgba(255,255,255,0.04); border-radius:8px; padding:9px; }
.dcard.full { grid-column:span 2; }
.dc-lbl { font-size:9px; color:#475569; text-transform:uppercase; letter-spacing:.5px; }
.dc-val { font-size:12.5px; font-weight:600; color:#e2e8f0; margin-top:3px; }
.dc-val.g { color:#10b981; }

.eco-badge {
    display:inline-block; font-size:10px; padding:4px 10px; border-radius:20px; font-weight:600;
    background:rgba(16,185,129,0.12); color:#34d399; border:1px solid rgba(16,185,129,0.25); margin-bottom:6px;
}
.eco-desc { font-size:11.5px; color:#94a3b8; line-height:1.6; }

/* ── Tags (flora/fauna) ───────────── */
.tags { display:flex; flex-wrap:wrap; gap:5px; margin-top:4px; }
.tag { font-size:10px; padding:3px 8px; border-radius:12px; font-weight:500; }
.fl  { background:rgba(16,185,129,0.1);   color:#34d399; border:1px solid rgba(16,185,129,0.2); }
.fa  { background:rgba(14,165,233,0.1);   color:#38bdf8; border:1px solid rgba(14,165,233,0.2); }

/* ── Progress Bars ────────────────── */
.pbars { display:flex; flex-direction:column; gap:7px; margin-top:4px; }
.pb-item {}
.pb-row  { display:flex; justify-content:space-between; font-size:10px; color:#94a3b8; margin-bottom:3px; }
.pb-track { height:5px; background:rgba(255,255,255,0.07); border-radius:3px; overflow:hidden; }
.pb-fill  { height:100%; border-radius:3px; transition:width .7s cubic-bezier(.16,1,.3,1); }

/* ── CAROUSEL ─────────────────────── */
.carousel-wrap {
    position:relative; border-radius:10px; overflow:hidden;
    height:170px; background:#060b14;
    box-shadow:0 4px 20px rgba(0,0,0,0.5);
}
.carousel-track { display:flex; height:100%; transition:transform .55s cubic-bezier(.4,0,.2,1); }
.carousel-slide {
    min-width:100%; height:100%; flex-shrink:0; position:relative;
}
.carousel-slide img {
    width:100%; height:100%; object-fit:cover;
    transition:transform 6s ease; transform:scale(1.04);
}
.carousel-slide.active img { transform:scale(1); }
.carousel-caption {
    position:absolute; bottom:0; left:0; right:0; padding:20px 12px 10px;
    background:linear-gradient(transparent, rgba(5,8,16,0.9));
}
.cap-tipo  { font-size:9px; color:#10b981; font-weight:700; text-transform:uppercase; letter-spacing:.7px; }
.cap-label { font-size:12px; font-weight:600; color:#f8fafc; font-style:italic; margin-top:2px; }

/* Dots */
.car-dots { display:flex; justify-content:center; gap:6px; padding:7px 0 3px; }
.car-dot { width:5px; height:5px; border-radius:50%; background:rgba(255,255,255,0.2); cursor:pointer; transition:.2s; }
.car-dot.on { background:#10b981; width:16px; border-radius:3px; }

/* Arrows */
.car-arr {
    position:absolute; top:50%; transform:translateY(-50%);
    width:28px; height:28px; border-radius:50%; cursor:pointer;
    background:rgba(10,15,30,0.6); border:1px solid rgba(255,255,255,0.12);
    backdrop-filter:blur(6px); color:#e2e8f0; font-size:12px;
    display:flex; align-items:center; justify-content:center;
    z-index:2; transition:.2s; user-select:none;
}
.car-arr:hover { background:rgba(16,185,129,0.25); border-color:#10b981; }
.car-arr.prev { left:7px; }
.car-arr.next { right:7px; }

/* ── HOVER TOOLTIP CUSTOM ──────────── */
#hover-tip {
    position:absolute; z-index:999; pointer-events:none;
    min-width:220px; max-width:260px; padding:0;
    border-radius:12px; overflow:hidden;
    box-shadow:0 12px 40px rgba(0,0,0,0.7);
    border:1px solid rgba(255,255,255,0.1);
    transition:opacity .18s, transform .18s;
    opacity:0; transform:translateY(8px) scale(.97);
    background:rgba(8,13,25,0.95);
    backdrop-filter:blur(18px);
}
#hover-tip.show { opacity:1; transform:translateY(0) scale(1); }
.ht-img { width:100%; height:90px; object-fit:cover; }
.ht-body { padding:10px 12px 12px; }
.ht-id  { font-family:monospace; font-size:9px; color:#10b981; font-weight:700; letter-spacing:.5px; }
.ht-mun { font-size:11px; font-weight:600; color:#f1f5f9; margin:3px 0 4px; }
.ht-eco { font-size:10px; color:#10b981; font-style:italic; margin-bottom:6px;
    padding:3px 7px; background:rgba(16,185,129,0.1); border-radius:4px;
    border:1px solid rgba(16,185,129,0.2); display:inline-block; }
.ht-area { font-size:10.5px; color:#64748b; }
.ht-area span { color:#e2e8f0; font-weight:600; }

/* ── Compass ──────────────────────── */
.compass {
    position:absolute; bottom:22px; left:340px; width:64px; height:64px;
    z-index:1000; pointer-events:none;
    filter:drop-shadow(0 4px 12px rgba(0,0,0,0.7));
}

/* ── Legend pill ──────────────────── */
.leg-pill {
    position:absolute; bottom:22px; left:416px; z-index:1000;
    padding:10px 14px; border-radius:10px;
    font-size:10px; display:none;
}
.leg-pill.show { display:block; }
.li { display:flex; align-items:center; gap:7px; color:#cbd5e1; margin-bottom:5px; }
.li:last-child { margin-bottom:0; }
.lsw { width:16px; height:8px; border-radius:2px; }
</style>

<!-- Chart.js CDN -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- HEADER -->
<div class="hdr gp">
  <div class="hdr-left">
    <div class="hdr-icon">🌲</div>
    <div>
      <div class="hdr-name">Área Natural Protegida · Archipiélago</div>
      <div class="hdr-sub">Corredor Biológico Multifuncional · Región Capital, Veracruz</div>
    </div>
  </div>
  <div class="hdr-kpis">
    <div class="kpi"><div class="kpi-lbl">Superficie</div><div class="kpi-val green" id="kpi-ha">5,674 ha</div></div>
    <div class="kpi"><div class="kpi-lbl">Fragmentos</div><div class="kpi-val" id="kpi-frags">20</div></div>
    <div class="kpi"><div class="kpi-lbl">Municipios</div><div class="kpi-val">5</div></div>
    <div class="kpi"><div class="kpi-lbl">Decreto</div><div class="kpi-val" style="font-size:12px">Ene 2015</div></div>
  </div>
</div>

<!-- SIDEBAR IZQUIERDO -->
<div class="sb sb-left gp">
  <!-- Búsqueda -->
  <div class="srch-wrap">
    <span class="srch-ico">🔍</span>
    <input id="srch" class="srch-inp" placeholder="Buscar fragmento o municipio…" />
    <div id="srch-dd" class="srch-dd"></div>
  </div>

  <!-- Filtros municipio -->
  <div>
    <div class="sec">Filtrar por Municipio</div>
    <div class="ftrs">
      <button class="ftr on"  onclick="setFilter('todos',this)">Todos</button>
      <button class="ftr"     onclick="setFilter('Xalapa',this)">Xalapa</button>
      <button class="ftr"     onclick="setFilter('Coatepec',this)">Coatepec</button>
      <button class="ftr"     onclick="setFilter('Banderilla',this)">Banderilla</button>
      <button class="ftr"     onclick="setFilter('Tlalnelhuayocan',this)">Tlalnelhuayocan</button>
      <button class="ftr"     onclick="setFilter('Emiliano Zapata',this)">E. Zapata</button>
    </div>
  </div>

  <!-- Capas -->
  <div>
    <div class="sec">Capas del Mapa</div>
    <div class="ltgs">
      <div class="ltg" id="tgl-anp" onclick="toggleLayer('ANP Archipiélago',this)">
        <div class="chk on"></div><span>ANP Archipiélago</span>
        <div class="ldot" style="background:#10b981;box-shadow:0 0 6px #10b981;"></div>
      </div>
      <div class="ltg" id="tgl-mun" onclick="toggleLayer('Municipios',this)">
        <div class="chk on"></div><span>Límites Municipales</span>
        <div class="ldot" style="border:2px dashed #60a5fa;background:transparent;border-radius:50%;"></div>
      </div>
      <div class="ltg off" id="tgl-uso" onclick="toggleLayer('Uso de Suelo',this)">
        <div class="chk"></div><span>Uso de Suelo (INEGI)</span>
        <div class="ldot" style="background:linear-gradient(135deg,#d97706,#059669);"></div>
      </div>
      <div class="ltg off" id="tgl-rio" onclick="toggleLayer('Ríos',this)">
        <div class="chk"></div><span>Red de Ríos</span>
        <div class="ldot" style="background:#38bdf8;"></div>
      </div>
    </div>
  </div>

  <!-- Mapas base -->
  <div>
    <div class="sec">Mapa de Fondo</div>
    <div class="bms">
      <button class="bm on"  onclick="setBase('oscuro',this)">🌑 Oscuro</button>
      <button class="bm"     onclick="setBase('sat',this)">🛰 Satélite</button>
      <button class="bm"     onclick="setBase('topo',this)">🗺 Terreno</button>
    </div>
  </div>

  <!-- Gráfico municipios -->
  <div>
    <div class="sec">Área por Municipio (ha)</div>
    <div class="chart-box"><canvas id="ch-mun"></canvas></div>
  </div>

  <!-- Gráfico uso de suelo -->
  <div>
    <div class="sec">Uso de Suelo Global ANP</div>
    <div class="chart-box"><canvas id="ch-uso"></canvas></div>
  </div>
</div>

<!-- SIDEBAR DERECHO -->
<div class="sb sb-right gp" id="sb-right">
  <!-- Placeholder -->
  <div class="placeholder" id="ph">
    <div class="ph-icon">📍</div>
    <div class="sec" style="border:none;margin-bottom:8px;">Ficha Ecológica</div>
    <p class="ph-txt">Haz clic o pasa el cursor sobre cualquier polígono verde del mapa para ver los detalles de ese fragmento y el carrusel de su biodiversidad.</p>
  </div>

  <!-- Detalle fragmento -->
  <div id="det" style="display:none;" class="det">
    <!-- Header -->
    <div class="det-hdr">
      <div>
        <span class="bid" id="d-id">FRAG_00</span>
        <div class="det-title" id="d-title">Fragmento</div>
        <div class="det-mun" id="d-mun">Municipio</div>
      </div>
    </div>

    <!-- CARRUSEL -->
    <div>
      <div class="sec">Biodiversidad · Galería</div>
      <div class="carousel-wrap" id="car-wrap">
        <div class="carousel-track" id="car-track"></div>
        <div class="car-arr prev" id="car-prev">&#8249;</div>
        <div class="car-arr next" id="car-next">&#8250;</div>
      </div>
      <div class="car-dots" id="car-dots"></div>
    </div>

    <!-- Métricas -->
    <div class="dgrid">
      <div class="dcard"><div class="dc-lbl">Superficie</div><div class="dc-val g" id="d-area">—</div></div>
      <div class="dcard"><div class="dc-lbl">Coordenadas</div><div class="dc-val" id="d-coor" style="font-size:10.5px;">—</div></div>
    </div>

    <!-- Ecosistema -->
    <div>
      <div class="sec">Ecosistema Dominante</div>
      <div class="eco-badge" id="d-ecobadge">—</div>
      <div class="eco-desc"  id="d-ecodesc">—</div>
    </div>

    <!-- Flora -->
    <div>
      <div class="sec">Flora Representativa</div>
      <div class="tags" id="d-flora"></div>
    </div>

    <!-- Fauna -->
    <div>
      <div class="sec">Fauna Destacada</div>
      <div class="tags" id="d-fauna"></div>
    </div>

    <!-- Uso de suelo local -->
    <div>
      <div class="sec">Composición Uso de Suelo</div>
      <div class="pbars" id="d-pbars"></div>
    </div>
  </div>
</div>

<!-- HOVER TOOLTIP -->
<div id="hover-tip">
  <img id="ht-img" class="ht-img" src="" alt="" />
  <div class="ht-body">
    <div class="ht-id"  id="ht-id">FRAG_00</div>
    <div class="ht-mun" id="ht-mun">—</div>
    <div class="ht-eco" id="ht-eco">—</div>
    <div class="ht-area">Superficie: <span id="ht-area">—</span></div>
  </div>
</div>

<!-- ROSA DE LOS VIENTOS -->
<svg class="compass" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="47" fill="rgba(8,13,25,0.88)" stroke="rgba(255,255,255,0.08)" stroke-width="1.5"/>
  <polygon points="50,9 55,44 50,50 45,44" fill="#10b981"/>
  <polygon points="50,91 55,56 50,50 45,56" fill="rgba(255,255,255,0.18)"/>
  <polygon points="91,50 56,45 50,50 56,55" fill="rgba(255,255,255,0.14)"/>
  <polygon points="9,50  44,45 50,50 44,55" fill="rgba(255,255,255,0.14)"/>
  <polygon points="50,28 52,44 50,50 48,44" fill="#0d9f72" opacity=".6"/>
  <text x="50" y="7.5" text-anchor="middle" font-family="Outfit,sans-serif" font-size="10.5" font-weight="700" fill="#10b981">N</text>
  <text x="50" y="98.5" text-anchor="middle" font-family="Outfit,sans-serif" font-size="8" font-weight="600" fill="rgba(255,255,255,0.35)">S</text>
  <text x="96" y="53.5" text-anchor="middle" font-family="Outfit,sans-serif" font-size="8" font-weight="600" fill="rgba(255,255,255,0.35)">E</text>
  <text x="4"  y="53.5" text-anchor="middle" font-family="Outfit,sans-serif" font-size="8" font-weight="600" fill="rgba(255,255,255,0.35)">O</text>
  <circle cx="50" cy="50" r="2.8" fill="#fff" opacity=".9"/>
</svg>

<!-- Leyenda Uso Suelo -->
<div class="leg-pill gp" id="leg-uso">
  <div class="li"><div class="lsw" style="background:#059669;"></div>Bosques de Niebla</div>
  <div class="li"><div class="lsw" style="background:#d97706;"></div>Cafetales / Agrícola</div>
  <div class="li"><div class="lsw" style="background:#84cc16;"></div>Pastizales</div>
  <div class="li"><div class="lsw" style="background:#9ca3af;"></div>Asentamientos</div>
  <div class="li"><div class="lsw" style="background:#3b82f6;"></div>Agua</div>
</div>
<div class="leg-pill gp" id="leg-rio" style="bottom:115px;">
  <div class="li"><div class="lsw" style="background:#38bdf8;height:3px;"></div>Corriente de Agua</div>
</div>

<script>
// ── DATOS INYECTADOS POR PYTHON ───────────────────────────────────────────────
var STATS_MUN      = __STATS_MUN__;
var STATS_USO      = __STATS_USO__;
var CAROUSEL_DATA  = __CAROUSEL_DATA__;
var anpGeoLayer    = null;
var selectedLayer  = null;
var activeFilter   = 'todos';
var baseLayers     = {};
var carIdx         = 0;
var carSlides      = [];
var carTimer       = null;

// ── HELPER: get Leaflet map ────────────────────────────────────────────────────
function getMap() {
    for (var k in window) {
        var o = window[k];
        if (o && o._leaflet_id && typeof o.eachLayer==='function' && typeof o.getCenter==='function') return o;
    }
    return null;
}

// ── SETUP ──────────────────────────────────────────────────────────────────────
function setup() {
    var map = getMap();
    if (!map) { setTimeout(setup, 120); return; }

    // Move zoom to bottom-right
    L.control.zoom({position:'bottomright'}).addTo(map);

    // Find & wire ANP layer
    map.eachLayer(function(lyr) {
        var n = lyr.options && lyr.options.name;
        if (n && (n.indexOf('ANP') !== -1)) {
            anpGeoLayer = lyr;
            lyr.eachLayer(function(sub) {
                sub.on('mousemove', onHover);
                sub.on('mouseout',  onHoverOut);
                sub.on('click',     onClick);
            });
        }
    });

    setupBasemaps();
    buildSearchIndex();
    drawCharts();
    setTimeout(function(){ if(anpGeoLayer) anpGeoLayer.bringToFront(); }, 800);
}

// ── BASEMAPS ───────────────────────────────────────────────────────────────────
function setupBasemaps() {
    var map = getMap(); if (!map) return;
    baseLayers.oscuro = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        {attribution:'&copy; CARTO, OpenStreetMap'});
    baseLayers.sat    = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {attribution:'&copy; Esri'});
    baseLayers.topo   = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        {attribution:'&copy; OpenStreetMap'});

    map.eachLayer(function(l){ if(l instanceof L.TileLayer) map.removeLayer(l); });
    baseLayers.oscuro.addTo(map);
}

function setBase(key, btn) {
    var map = getMap(); if(!map) return;
    Object.values(baseLayers).forEach(function(l){ map.removeLayer(l); });
    baseLayers[key].addTo(map);
    if(anpGeoLayer) anpGeoLayer.bringToFront();
    document.querySelectorAll('.bm').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
}

// ── LAYER TOGGLE ───────────────────────────────────────────────────────────────
function findCB(name) {
    var labels = document.querySelectorAll('.leaflet-control-layers-overlays label');
    for(var i=0;i<labels.length;i++){
        var s = labels[i].querySelector('span');
        if(s && s.textContent.trim()===name) return labels[i].querySelector('input[type=checkbox]');
    }
    return null;
}

function toggleLayer(name, el) {
    var cb = findCB(name);
    if(!cb){ var a=name==='ANP Archipiélago'?'ANP Archipi\u00e9lago':name==='Ríos'?'R\u00edos':name; cb=findCB(a); }
    if(!cb) return;
    cb.click();
    var on = cb.checked;
    var chk = el.querySelector('.chk');
    if(on){ chk.classList.add('on'); el.classList.remove('off'); } else { chk.classList.remove('on'); el.classList.add('off'); }
    if(name==='Uso de Suelo'){ document.getElementById('leg-uso').classList.toggle('show',on); if(on&&anpGeoLayer) setTimeout(function(){anpGeoLayer.bringToFront();},120); }
    if(name==='Ríos')        { document.getElementById('leg-rio').classList.toggle('show',on); if(on&&anpGeoLayer) setTimeout(function(){anpGeoLayer.bringToFront();},120); }
}

// ── FILTER ─────────────────────────────────────────────────────────────────────
function setFilter(mun, btn) {
    activeFilter = mun;
    document.querySelectorAll('.ftr').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
    if(!anpGeoLayer) return;
    anpGeoLayer.eachLayer(function(sub){
        var p = sub.feature.properties;
        var match = (mun==='todos' || p.Nombre_Municipio===mun);
        sub.setStyle(match
            ? {fillOpacity:.6, opacity:1, weight:2.5}
            : {fillOpacity:.03, opacity:.08, weight:1});
    });
}

// ── SEARCH ─────────────────────────────────────────────────────────────────────
var searchIdx = [];
function buildSearchIndex() {
    if(!anpGeoLayer) return;
    anpGeoLayer.eachLayer(function(sub){
        var p = sub.feature.properties;
        searchIdx.push({id:p.Fragment_ID, mun:p.Nombre_Municipio, layer:sub,
            label:'Frag '+p.Fragment_ID+' ('+p.Nombre_Municipio+')'});
    });
}

document.getElementById('srch').addEventListener('input', function(){
    var q = this.value.toLowerCase().trim();
    var dd = document.getElementById('srch-dd');
    dd.innerHTML = '';
    if(!q){ dd.style.display='none'; return; }
    var hits = searchIdx.filter(function(x){ return x.label.toLowerCase().includes(q)||x.id.toLowerCase().includes(q)||x.mun.toLowerCase().includes(q); });
    if(!hits.length){ dd.innerHTML='<div class="srch-empty">Sin resultados</div>'; }
    else hits.forEach(function(h){
        var d=document.createElement('div'); d.className='srch-item'; d.textContent=h.label;
        d.onclick=function(){ onClick({target:h.layer}); document.getElementById('srch').value=h.label; dd.style.display='none'; };
        dd.appendChild(d);
    });
    dd.style.display='block';
});
document.addEventListener('click', function(e){ if(e.target.id!=='srch') document.getElementById('srch-dd').style.display='none'; });

// ── HOVER TOOLTIP ──────────────────────────────────────────────────────────────
var tip = document.getElementById('hover-tip');
var lastHovered = null;

function getHoverImage(props) {
    var key = props.Carousel_Key || 'bosque';
    var slides = CAROUSEL_DATA[key] || CAROUSEL_DATA['bosque'];
    return slides.length ? slides[0].src : '';
}

function onHover(e) {
    var layer = e.target;
    var props  = layer.feature.properties;

    if(layer !== selectedLayer) {
        layer.setStyle({fillColor:'#059669', fillOpacity:.8, weight:3.5, color:'#a7f3d0'});
    }
    lastHovered = layer;

    // Update tooltip content
    document.getElementById('ht-id').textContent   = props.Fragment_ID;
    document.getElementById('ht-mun').textContent  = props.Nombre_Municipio;
    document.getElementById('ht-eco').textContent  = props.Eco_Tipo;
    document.getElementById('ht-area').textContent = props['Area (Hectareas)'];
    var imgSrc = getHoverImage(props);
    document.getElementById('ht-img').src = imgSrc;
    document.getElementById('ht-img').style.display = imgSrc ? 'block' : 'none';

    tip.classList.add('show');
    positionTip(e.originalEvent);
}

function positionTip(e) {
    var x = e.clientX, y = e.clientY;
    var tw = tip.offsetWidth  || 250;
    var th = tip.offsetHeight || 170;
    var vw = window.innerWidth, vh = window.innerHeight;
    var left = x + 14;
    var top  = y - 20;
    if(left + tw > vw - 20) left = x - tw - 14;
    if(top  + th > vh - 20) top  = y - th + 20;
    tip.style.left = left + 'px';
    tip.style.top  = top  + 'px';
}

document.addEventListener('mousemove', function(e) {
    if(tip.classList.contains('show')) positionTip(e);
});

function onHoverOut(e) {
    if(e.target !== selectedLayer) {
        var p = e.target.feature.properties;
        var mun = p.Nombre_Municipio;
        var match = (activeFilter==='todos' || mun===activeFilter);
        e.target.setStyle({fillColor:'#10b981', color:'#34d399', weight:2.5,
            fillOpacity: match ? .6 : .03, opacity: match ? 1 : .08});
    }
    lastHovered = null;
    tip.classList.remove('show');
}

// ── CLICK → DETAILS PANEL ─────────────────────────────────────────────────────
function onClick(e) {
    var layer = e.target;
    var props  = layer.feature.properties;
    var map    = getMap();

    // Reset previous selection
    resetStyles();
    selectedLayer = layer;
    layer.setStyle({fillColor:'#00ffc4', color:'#fff', weight:3.5, fillOpacity:.88});
    if(map) map.fitBounds(layer.getBounds(), {padding:[30,30], maxZoom:15, animate:true, duration:.6});
    if(anpGeoLayer) anpGeoLayer.bringToFront();

    // Show panel
    document.getElementById('ph').style.display  = 'none';
    var det = document.getElementById('det');
    det.style.display = 'flex';
    det.classList.remove('det'); void det.offsetWidth; det.classList.add('det'); // re-trigger animation

    document.getElementById('d-id').textContent      = props.Fragment_ID;
    document.getElementById('d-title').textContent   = 'Fragmento ' + props.Fragment_ID;
    document.getElementById('d-mun').textContent     = '📍 ' + props.Nombre_Municipio;
    document.getElementById('d-area').textContent    = props['Area (Hectareas)'];
    document.getElementById('d-coor').textContent    = props.Coordenadas;
    document.getElementById('d-ecobadge').textContent = props.Eco_Tipo;
    document.getElementById('d-ecodesc').textContent  = props.Eco_Desc;

    // Flora tags
    var fc = document.getElementById('d-flora'); fc.innerHTML='';
    props.Flora.split(',').forEach(function(t){
        var s=document.createElement('span'); s.className='tag fl'; s.textContent=t.trim(); fc.appendChild(s);
    });

    // Fauna tags
    var fac = document.getElementById('d-fauna'); fac.innerHTML='';
    props.Fauna.split(',').forEach(function(t){
        var s=document.createElement('span'); s.className='tag fa'; s.textContent=t.trim(); fac.appendChild(s);
    });

    // Progress bars land use
    var pbc = document.getElementById('d-pbars'); pbc.innerHTML='';
    try {
        var uso = JSON.parse(props.Uso_JSON);
        var sorted = Object.entries(uso).sort(function(a,b){return b[1]-a[1];}).slice(0,5);
        sorted.forEach(function(entry){
            var cat=entry[0], pct=entry[1];
            var short = cat.replace(/VEGETACI.N SECUNDARIA/gi,'Veg. Sec.')
                           .replace(/BOSQUE MES.FILO DE MONTA.A/gi,'Bosque Niebla')
                           .replace(/AGRICULTURA DE TEMPORAL PERMANENTE/gi,'Cafetal Sombra')
                           .replace(/AGRICULTURA DE TEMPORAL SEMIPERMANENTE Y PERMANENTE/gi,'Agr. Semi/Perm.')
                           .replace(/AGRICULTURA DE TEMPORAL/gi,'Agr. Temporal')
                           .replace(/PASTIZAL CULTIVADO/gi,'Pastizal')
                           .replace(/ASENTAMIENTOS HUMANOS/gi,'Asentamientos')
                           .replace(/CUERPO DE AGUA/gi,'Agua')
                           .replace(/DE BOSQUE MES.FILO DE MONTA.A/gi,'');
            var color = getUsoColor(cat);
            var div = document.createElement('div'); div.className='pb-item';
            div.innerHTML = '<div class="pb-row"><span>'+short+'</span><span>'+pct+'%</span></div>'+
                '<div class="pb-track"><div class="pb-fill" style="width:0%;background:'+color+';" data-w="'+pct+'"></div></div>';
            pbc.appendChild(div);
        });
        // Animate bars
        setTimeout(function(){
            pbc.querySelectorAll('.pb-fill').forEach(function(b){ b.style.width=b.dataset.w+'%'; });
        }, 80);
    } catch(err){}

    // Build carousel
    buildCarousel(props.Carousel_Key);
}

function getUsoColor(d) {
    d=d.toUpperCase();
    if(d.includes('ASENTAMIENTOS')||d.includes('URBANO')) return '#9ca3af';
    if(d.includes('AGUA')) return '#3b82f6';
    if(d.includes('BOSQUE')&&!d.includes('SECUNDARIA')) return '#059669';
    if(d.includes('SELVA')&&!d.includes('SECUNDARIA')) return '#16a34a';
    if(d.includes('AGRICULTURA')) return '#d97706';
    if(d.includes('PASTIZAL')) return '#84cc16';
    if(d.includes('SECUNDARIA')||d.includes('VEGETAC')) return '#65a30d';
    return '#64748b';
}

function resetStyles() {
    if(!anpGeoLayer) return;
    anpGeoLayer.eachLayer(function(sub){
        var p=sub.feature.properties;
        var match = (activeFilter==='todos' || p.Nombre_Municipio===activeFilter);
        sub.setStyle({fillColor:'#10b981', color:'#34d399', weight:2.5,
            fillOpacity: match?.6:.03, opacity: match?1:.08});
    });
}

// ── CARRUSEL ───────────────────────────────────────────────────────────────────
function buildCarousel(key) {
    var slides = CAROUSEL_DATA[key] || CAROUSEL_DATA['bosque'];
    carSlides  = slides;
    carIdx     = 0;
    if(carTimer) clearInterval(carTimer);

    var track = document.getElementById('car-track');
    var dots  = document.getElementById('car-dots');
    track.innerHTML = ''; dots.innerHTML = '';

    slides.forEach(function(s, i){
        var slide = document.createElement('div');
        slide.className = 'carousel-slide' + (i===0?' active':'');
        var img = document.createElement('img');
        img.src = s.src; img.alt = s.label;
        var cap = document.createElement('div');
        cap.className = 'carousel-caption';
        cap.innerHTML = '<div class="cap-tipo">'+s.tipo+'</div><div class="cap-label"><em>'+s.label+'</em></div>';
        slide.appendChild(img); slide.appendChild(cap);
        track.appendChild(slide);

        var dot = document.createElement('div');
        dot.className = 'car-dot' + (i===0?' on':'');
        dot.onclick   = (function(idx){ return function(){ goSlide(idx); }; })(i);
        dots.appendChild(dot);
    });

    updateCarousel();
    carTimer = setInterval(function(){ goSlide((carIdx+1) % carSlides.length); }, 4000);
}

function goSlide(n) {
    carIdx = (n + carSlides.length) % carSlides.length;
    updateCarousel();
    if(carTimer) clearInterval(carTimer);
    carTimer = setInterval(function(){ goSlide((carIdx+1) % carSlides.length); }, 4000);
}

function updateCarousel() {
    var track  = document.getElementById('car-track');
    var dots   = document.querySelectorAll('.car-dot');
    var slides = document.querySelectorAll('.carousel-slide');
    track.style.transform = 'translateX(-' + (carIdx * 100) + '%)';
    slides.forEach(function(s,i){ s.classList.toggle('active', i===carIdx); });
    dots.forEach(function(d,i){ d.classList.toggle('on', i===carIdx); });
}

document.getElementById('car-prev').onclick = function(){ goSlide(carIdx-1); };
document.getElementById('car-next').onclick = function(){ goSlide(carIdx+1); };

// ── CHARTS ─────────────────────────────────────────────────────────────────────
function drawCharts() {
    var ctxMun = document.getElementById('ch-mun').getContext('2d');
    new Chart(ctxMun, {
        type: 'doughnut',
        data: {
            labels: Object.keys(STATS_MUN),
            datasets: [{
                data: Object.values(STATS_MUN),
                backgroundColor: ['rgba(16,185,129,.8)','rgba(59,130,246,.8)','rgba(245,158,11,.8)','rgba(139,92,246,.8)','rgba(236,72,153,.8)'],
                borderWidth: 1.5, borderColor: '#080d19', hoverOffset: 5
            }]
        },
        options: {
            responsive:true, maintainAspectRatio:false, cutout:'68%',
            plugins: {
                legend:{ position:'right', labels:{ color:'#94a3b8', font:{size:9,family:'Inter'}, boxWidth:8, padding:5 }},
                tooltip:{ backgroundColor:'rgba(8,13,25,.95)', titleColor:'#f8fafc', bodyColor:'#cbd5e1',
                    borderColor:'rgba(255,255,255,.08)', borderWidth:1,
                    callbacks:{ label:function(c){ return ' '+c.label+': '+c.raw+' ha'; }}}
            }
        }
    });

    var ctxUso = document.getElementById('ch-uso').getContext('2d');
    new Chart(ctxUso, {
        type: 'bar',
        data: {
            labels: Object.keys(STATS_USO),
            datasets:[{
                data: Object.values(STATS_USO),
                backgroundColor:['rgba(5,150,105,.85)','rgba(217,119,6,.85)','rgba(132,204,22,.85)','rgba(156,163,175,.85)','rgba(59,130,246,.85)'],
                borderRadius:4, borderWidth:0
            }]
        },
        options: {
            indexAxis:'y', responsive:true, maintainAspectRatio:false,
            scales:{
                x:{ grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#64748b',font:{size:8}} },
                y:{ grid:{display:false}, ticks:{color:'#cbd5e1',font:{size:9,weight:'500'}} }
            },
            plugins:{ legend:{display:false},
                tooltip:{ backgroundColor:'rgba(8,13,25,.95)', titleColor:'#f8fafc', bodyColor:'#cbd5e1',
                    borderColor:'rgba(255,255,255,.08)', borderWidth:1,
                    callbacks:{ label:function(c){ return ' '+c.raw+' ha'; }}}}
        }
    });
}

// ── INIT ───────────────────────────────────────────────────────────────────────
window.addEventListener('load', function(){ setTimeout(setup, 500); });
</script>
"""

# ─── INYECTAR JSON DESDE PYTHON ───────────────────────────────────────────────
DASHBOARD = DASHBOARD.replace("__STATS_MUN__",     json.dumps(stats_mun))
DASHBOARD = DASHBOARD.replace("__STATS_USO__",     json.dumps(global_uso))
DASHBOARD = DASHBOARD.replace("__CAROUSEL_DATA__", json.dumps(carousel_json))

m.get_root().html.add_child(Element(DASHBOARD))

archivo_salida = "index.html"
m.save(archivo_salida)
print(f"\n¡Listo! Dashboard guardado como '{archivo_salida}'.")
