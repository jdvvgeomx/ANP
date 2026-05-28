import geopandas as gpd
import folium
from folium import Element
import warnings
import pandas as pd

# Colores oficiales por tipo de uso de suelo (INEGI)
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
    else:
        return '#57534e'

print("Cargando archivos Shapefile...")
anp       = gpd.read_file("ANP Archipielago.shp",    encoding='latin1')
uso_suelo = gpd.read_file("Uso_de_sueloANPABYS.shp", encoding='latin1')
rios      = gpd.read_file("Rios.shp",                encoding='latin1')

municipios_nombres = ["Xalapa", "Coatepec", "Emiliano_Zapata", "Banderilla", "Tlalnelhuayocan"]
municipios_gdfs = []
for nombre in municipios_nombres:
    m_gdf = gpd.read_file(f"{nombre}.shp", encoding='latin1')
    m_gdf['Nombre_Municipio'] = nombre.replace("_", " ")
    m_gdf = m_gdf[['Nombre_Municipio', 'geometry']]
    municipios_gdfs.append(m_gdf)
municipios = pd.concat(municipios_gdfs, ignore_index=True)

print("Procesando datos espaciales...")
anp_utm        = anp.to_crs(epsg=32614)
municipios_utm = municipios.to_crs(epsg=32614)
anp_utm.geometry        = anp_utm.geometry.buffer(0)
municipios_utm.geometry = municipios_utm.geometry.buffer(0)

anp_individual   = anp_utm.explode(index_parts=False)
anp_intersectado = gpd.overlay(anp_individual, municipios_utm, how='intersection')

area_hectareas = anp_intersectado.area / 10000
anp_intersectado['Area (Hectareas)'] = area_hectareas.round(2).astype(str) + " ha"

anp_wgs84_temp = anp_intersectado.to_crs(epsg=4326)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    puntos = anp_wgs84_temp.geometry.representative_point()
    anp_intersectado['Coordenadas'] = (
        puntos.y.round(5).astype(str) + "\u00b0, " + puntos.x.round(5).astype(str) + "\u00b0"
    )

anp_intersectado['Flora']      = "(Por definir)"
anp_intersectado['Fauna']      = "(Por definir)"
anp_intersectado['Nombre_ANP'] = "Fragmento de ANP Archipi\u00e9lago"

print("Transformando a WGS84...")
anp_final        = anp_intersectado.to_crs(epsg=4326)
municipios_wgs84 = municipios_utm.to_crs(epsg=4326)
uso_suelo_wgs84  = uso_suelo.to_crs(epsg=4326)
rios_wgs84       = rios.to_crs(epsg=4326)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    bounds   = anp_final.total_bounds
    centro_y = (bounds[1] + bounds[3]) / 2
    centro_x = (bounds[0] + bounds[2]) / 2

print("Generando el mapa...")
m = folium.Map(location=[centro_y, centro_x], tiles='CartoDB dark_matter', control_scale=True)
margen = 0.04
m.fit_bounds([[bounds[1]-margen, bounds[0]-margen], [bounds[3]+margen, bounds[2]+margen]])

estilo_tooltip = (
    "background-color: #0f172a; color: #f1f5f9; font-family: 'Inter','Segoe UI',sans-serif; "
    "font-size: 13px; padding: 14px 16px; border-radius: 10px; "
    "box-shadow: 0 8px 20px rgba(0,0,0,0.7); border: 1px solid #1e40af; min-width: 200px;"
)

# ─── CAPAS ────────────────────────────────────────────────────────────────────
# ORDEN IMPORTANTE: las capas se apilan de abajo hacia arriba.
# Uso de Suelo y Ríos van primero (fondo), ANP va al último (encima siempre).

# 1. Uso de Suelo (apagado por defecto)
folium.GeoJson(
    uso_suelo_wgs84,
    name="Uso de Suelo",
    show=False,
    style_function=lambda feature: {
        'fillColor': color_uso_suelo(feature['properties']['DESCRIPCIO']),
        'color':     color_uso_suelo(feature['properties']['DESCRIPCIO']),
        'weight': 0.3,
        'fillOpacity': 0.45
    },
    highlight_function=lambda feature: {
        'fillOpacity': 0.75, 'weight': 1.5, 'color': '#ffffff'
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['DESCRIPCIO'],
        aliases=['<b>Uso de Suelo:</b>'],
        style=estilo_tooltip
    )
).add_to(m)

# 2. R\u00edos (apagado por defecto)
folium.GeoJson(
    rios_wgs84,
    name="R\u00edos",
    show=False,
    style_function=lambda feature: {
        'color': '#38bdf8',
        'weight': 1.2,
        'opacity': 0.75
    },
    highlight_function=lambda feature: {
        'color': '#7dd3fc', 'weight': 2.5, 'opacity': 1
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['NOM_RIO', 'NOM_TIPO'],
        aliases=['<b>Rio:</b>', '<b>Tipo:</b>'],
        style=estilo_tooltip
    )
).add_to(m)

# 3. Municipios
folium.GeoJson(
    municipios_wgs84,
    name="Municipios",
    show=True,
    style_function=lambda feature: {
        'fillColor': 'transparent',
        'color': '#60a5fa',
        'weight': 2,
        'fillOpacity': 0,
        'dashArray': '6 4'
    },
    highlight_function=lambda feature: {
        'fillColor': '#3b82f6', 'fillOpacity': 0.08, 'weight': 3, 'color': '#93c5fd'
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['Nombre_Municipio'],
        aliases=['<b>Municipio:</b>'],
        style=estilo_tooltip
    )
).add_to(m)

# 4. ANP Archipi\u00e9lago \u2014 protagonista absoluto, siempre al \u00faltimo = encima de todo
folium.GeoJson(
    anp_final,
    name="ANP Archipi\u00e9lago",
    show=True,
    style_function=lambda feature: {
        'fillColor': '#10b981',
        'color': '#34d399',
        'weight': 3,
        'fillOpacity': 0.65
    },
    highlight_function=lambda feature: {
        'fillColor': '#6ee7b7', 'fillOpacity': 0.92, 'weight': 5, 'color': '#a7f3d0'
    },
    tooltip=folium.GeoJsonTooltip(
        fields=['Nombre_ANP','Nombre_Municipio','Area (Hectareas)','Coordenadas','Flora','Fauna'],
        aliases=['<b>Fragmento:</b>','<b>Municipio:</b>','<b>Area:</b>',
                 '<b>Ubicacion (Lat, Lon):</b>','<b>Flora:</b>','<b>Fauna:</b>'],
        style=estilo_tooltip
    )
).add_to(m)

# LayerControl de Folium (oculto con CSS, solo se usa para su JS interno)
folium.LayerControl(collapsed=False).add_to(m)

# ─── DASHBOARD HTML ───────────────────────────────────────────────────────────
dashboard_html = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { box-sizing: border-box; }
body { font-family: 'Inter', sans-serif; margin: 0; }

/* Ocultar LayerControl nativo de Folium */
.leaflet-control-layers { display: none !important; }
.leaflet-top.leaflet-left  { top: 80px !important; }
.leaflet-bottom.leaflet-left { bottom: 10px; }

/* HEADER */
.hdr {
    position:absolute; top:0; left:0; width:100%; height:64px;
    background:linear-gradient(135deg,#0a0f1e,#0f172a);
    z-index:9999; color:#fff; display:flex; align-items:center;
    padding:0 24px; box-shadow:0 2px 20px rgba(0,0,0,.8);
    border-bottom:1px solid rgba(16,185,129,.3);
}
.hdr-icon {
    background:linear-gradient(135deg,#059669,#10b981);
    border-radius:10px; width:42px; height:42px;
    display:flex; align-items:center; justify-content:center;
    margin-right:16px; font-size:20px;
    box-shadow:0 0 15px rgba(16,185,129,.5);
}
.hdr-title { font-size:17px; font-weight:700; letter-spacing:.3px; }
.hdr-sub   { font-size:12px; color:#34d399; font-weight:500; margin-top:2px; }

/* PANEL CAPAS */
.layer-panel {
    position:absolute; top:85px; left:16px; z-index:9998;
    background:rgba(10,15,30,.93); border:1px solid rgba(255,255,255,.08);
    border-radius:14px; padding:14px 16px;
    backdrop-filter:blur(10px); box-shadow:0 8px 32px rgba(0,0,0,.6);
    min-width:215px;
}
.lp-title { font-size:10px; font-weight:700; color:#64748b; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:12px; }
.lbtn {
    display:flex; align-items:center; gap:10px;
    padding:9px 12px; margin-bottom:6px; border-radius:9px;
    cursor:pointer; border:1px solid transparent; transition:all .2s;
    font-size:13px; font-weight:500; color:#e2e8f0;
    background:rgba(255,255,255,.05); user-select:none;
}
.lbtn:last-child { margin-bottom:0; }
.lbtn:hover { background:rgba(255,255,255,.1); border-color:rgba(255,255,255,.12); }
.lbtn.on  { border-color:rgba(255,255,255,.15); background:rgba(255,255,255,.08); }
.lbtn.off { opacity:.4; }
.ldot { width:14px; height:14px; border-radius:3px; flex-shrink:0; }
.dot-anp { background:#10b981; box-shadow:0 0 8px rgba(16,185,129,.8); }
.dot-mun { background:transparent; border:2px dashed #60a5fa; }
.dot-uso { background:linear-gradient(135deg,#d97706,#059669); }
.tog { margin-left:auto; font-size:11px; }

/* LEYENDA */
.legend {
    position:absolute; bottom:36px; left:16px; z-index:9997;
    background:rgba(10,15,30,.93); border:1px solid rgba(255,255,255,.08);
    border-radius:14px; padding:14px 16px;
    backdrop-filter:blur(10px); box-shadow:0 8px 32px rgba(0,0,0,.6);
    width:215px;
}
.leg-title { font-size:10px; font-weight:700; color:#64748b; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:10px; }
.leg-sec   { font-size:10px; color:#475569; text-transform:uppercase; letter-spacing:1px; margin:10px 0 6px; font-weight:600; }
.leg-item  { display:flex; align-items:center; gap:9px; font-size:12px; color:#cbd5e1; margin-bottom:7px; }
.leg-item:last-child { margin-bottom:0; }
.sw     { width:18px; height:10px; border-radius:3px; flex-shrink:0; }
.sw-anp { background:#10b981; box-shadow:0 0 6px rgba(16,185,129,.6); }
.sw-mun { background:transparent; border:2px dashed #60a5fa; border-radius:3px; height:10px; }
.sw-rio { background:#38bdf8; height:3px; border-radius:2px; }

/* ROSA DE LOS VIENTOS */
.compass {
    position:absolute; bottom:36px; right:16px; z-index:9998;
    width:70px; height:70px;
    filter: drop-shadow(0 4px 10px rgba(0,0,0,0.7));
}
</style>

<!-- HEADER -->
<div class="hdr">
    <div class="hdr-icon">🌲</div>
    <div>
        <div class="hdr-title">Área Natural Protegida – Archipiélago</div>
        <div class="hdr-sub">Bosques y Selvas de la Región Capital · Veracruz, México</div>
    </div>
</div>

<!-- PANEL DE CAPAS -->
<div class="layer-panel">
    <div class="lp-title">Capas del Mapa</div>

    <div class="lbtn on" id="btn-anp" onclick="toggleLayer('ANP Archipi\u00e9lago','btn-anp','icon-anp')">
        <div class="ldot dot-anp"></div><span>ANP Archipiélago</span>
        <span class="tog" id="icon-anp">👁</span>
    </div>
    <div class="lbtn on" id="btn-mun" onclick="toggleLayer('Municipios','btn-mun','icon-mun')">
        <div class="ldot dot-mun"></div><span>Municipios</span>
        <span class="tog" id="icon-mun">👁</span>
    </div>
    <div class="lbtn off" id="btn-uso" onclick="toggleLayer('Uso de Suelo','btn-uso','icon-uso')">
        <div class="ldot dot-uso"></div><span>Uso de Suelo</span>
        <span class="tog" id="icon-uso">🔘</span>
    </div>
    <div class="lbtn off" id="btn-rio" onclick="toggleLayer('R\u00edos','btn-rio','icon-rio')">
        <div class="ldot" style="background:#38bdf8;height:4px;margin-top:5px;border-radius:2px;width:18px;"></div>
        <span>Ríos</span>
        <span class="tog" id="icon-rio">🔘</span>
    </div>
</div>

<!-- LEYENDA -->
<div class="legend">
    <div class="leg-title">Leyenda</div>
    <div class="leg-item"><div class="sw sw-anp"></div><span>ANP Archipiélago</span></div>
    <div class="leg-item"><div class="sw sw-mun"></div><span>Límite Municipal</span></div>
    <div class="leg-item" id="leg-rio" style="display:none;">
        <div class="sw sw-rio"></div><span>Ríos</span>
    </div>
    <div class="leg-sec" id="uso-sec" style="display:none;">Uso de Suelo (INEGI)</div>
    <div id="uso-items" style="display:none;">
        <div class="leg-item"><div class="sw" style="background:#9ca3af;"></div><span>Asentamientos Humanos</span></div>
        <div class="leg-item"><div class="sw" style="background:#d97706;"></div><span>Agricultura</span></div>
        <div class="leg-item"><div class="sw" style="background:#059669;"></div><span>Bosques</span></div>
        <div class="leg-item"><div class="sw" style="background:#16a34a;"></div><span>Selvas</span></div>
        <div class="leg-item"><div class="sw" style="background:#84cc16;"></div><span>Pastizales</span></div>
        <div class="leg-item"><div class="sw" style="background:#65a30d;"></div><span>Vegetación Secundaria</span></div>
        <div class="leg-item"><div class="sw" style="background:#3b82f6;"></div><span>Cuerpos de Agua</span></div>
    </div>
</div>

<!-- ROSA DE LOS VIENTOS (SVG inline) -->
<svg class="compass" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <!-- Fondo circular -->
  <circle cx="50" cy="50" r="48" fill="rgba(10,15,30,0.88)" stroke="rgba(255,255,255,0.12)" stroke-width="1.5"/>
  <!-- Puntas N-S (verde esmeralda = norte) -->
  <polygon points="50,8 56,44 50,50 44,44" fill="#10b981"/>
  <polygon points="50,92 56,56 50,50 44,56" fill="rgba(255,255,255,0.25)"/>
  <!-- Puntas E-W -->
  <polygon points="92,50 56,44 50,50 56,56" fill="rgba(255,255,255,0.18)"/>
  <polygon points="8,50 44,44 50,50 44,56"  fill="rgba(255,255,255,0.18)"/>
  <!-- Cruz de cuartos -->
  <polygon points="50,28 53,44 50,50 47,44" fill="#0d9f72" opacity="0.6"/>
  <!-- Letras cardinales -->
  <text x="50" y="7"  text-anchor="middle" font-family="Inter,sans-serif" font-size="11" font-weight="700" fill="#10b981">N</text>
  <text x="50" y="98" text-anchor="middle" font-family="Inter,sans-serif" font-size="9"  font-weight="600" fill="rgba(255,255,255,0.5)">S</text>
  <text x="95" y="54" text-anchor="middle" font-family="Inter,sans-serif" font-size="9"  font-weight="600" fill="rgba(255,255,255,0.5)">E</text>
  <text x="5"  y="54" text-anchor="middle" font-family="Inter,sans-serif" font-size="9"  font-weight="600" fill="rgba(255,255,255,0.5)">O</text>
  <!-- Punto central -->
  <circle cx="50" cy="50" r="3.5" fill="#fff" opacity="0.9"/>
</svg>

<script>
// ── Estado inicial (debe coincidir EXACTAMENTE con show=True/False en Python) ──
var layerState = {
    'ANP Archipi\u00e9lago': true,
    'Municipios':          true,
    'Uso de Suelo':        false,
    'R\u00edos':           false
};

// Elementos de leyenda que aparecen/desaparecen segun la capa
var legendMap = {
    'Uso de Suelo': ['uso-sec', 'uso-items'],
    'R\u00edos':    ['leg-rio']
};

// Busca el checkbox del LayerControl de Folium por nombre de capa
function findCheckbox(layerName) {
    var labels = document.querySelectorAll('.leaflet-control-layers-overlays label');
    for (var i = 0; i < labels.length; i++) {
        var span = labels[i].querySelector('span');
        if (span && span.textContent.trim() === layerName) {
            return labels[i].querySelector('input[type=checkbox]');
        }
    }
    return null;
}

// Llama bringToFront() en la capa ANP para mantenerla siempre visible
function bringANPToFront() {
    try {
        for (var k in window) {
            var obj = window[k];
            if (obj && obj._leaflet_id && typeof obj.eachLayer === 'function' &&
                typeof obj.getCenter === 'function') {
                obj.eachLayer(function(layer) {
                    if (layer.options && layer.options.name === 'ANP Archipi\u00e9lago') {
                        if (typeof layer.bringToFront === 'function') layer.bringToFront();
                    }
                });
                break;
            }
        }
    } catch(e) {}
}

function toggleLayer(layerName, btnId, iconId) {
    var cb = findCheckbox(layerName);
    if (cb) cb.click();   // activa/desactiva la capa en Leaflet

    // Invertir estado
    layerState[layerName] = !layerState[layerName];
    var isOn = layerState[layerName];

    // Actualizar botón
    var btn  = document.getElementById(btnId);
    var icon = document.getElementById(iconId);
    if (isOn) {
        btn.classList.add('on');
        btn.classList.remove('off');
        icon.innerHTML = '&#128065;';
    } else {
        btn.classList.remove('on');
        btn.classList.add('off');
        icon.innerHTML = '&#9898;';
    }

    // Mostrar/ocultar ítems en la leyenda
    var extras = legendMap[layerName];
    if (extras) {
        extras.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.style.display = isOn ? 'block' : 'none';
        });
    }

    // Siempre asegurar que el ANP quede encima de todo
    setTimeout(bringANPToFront, 80);
}

// Al cargar la página, asegurar que ANP esté al frente
window.addEventListener('load', function() {
    setTimeout(bringANPToFront, 1000);
});
</script>
"""

m.get_root().html.add_child(Element(dashboard_html))

archivo_salida = "mapa_archipielago.html"
m.save(archivo_salida)
print(f"¡Listo! Mapa guardado como '{archivo_salida}'.")
