"use client";
// Leaflet map for the console. Leaflet touches `window`, so it is imported inside effects only.
import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import type { AreaLake, AreaResult, Lake } from "@/lib/api";
import { sceneUrl } from "@/lib/api";

export const CLASS_COLOR: Record<AreaLake["class"], string> = { high: "#ff7a3d", watch: "#ffc24b", low: "#4fe3f0", stable: "#3ddc97" };

export type MapApi = { center: () => [number, number]; flyTo: (lat: number, lon: number, zoom?: number) => void; showPath: () => void };

type Props = {
  lake: Lake;
  sceneIdx: number;
  showWatched: boolean;
  area: AreaResult | null;
  selected: string | null;
  onSelect: (id: string) => void;
  onReady: (api: MapApi) => void;
};

export default function MapView({ lake, sceneIdx, showWatched, area, selected, onSelect, onReady }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const L = useRef<typeof Leaflet | null>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const watched = useRef<Leaflet.LayerGroup | null>(null);
  const scene = useRef<Leaflet.LayerGroup | null>(null);
  const areaLayer = useRef<Leaflet.LayerGroup | null>(null);
  const lakeLayers = useRef<Record<string, Leaflet.GeoJSON>>({});
  // Leaflet loads asynchronously: the layer effects below must run again once the map exists, or data that arrived
  // first (the lake outline, an area result) is never drawn.
  const [ready, setReady] = useState(false);

  // map + static watched-lake layers
  useEffect(() => {
    let alive = true;
    (async () => {
      const lib = (await import("leaflet")).default;
      if (!alive || !el.current || map.current) return;
      L.current = lib;
      const m = lib.map(el.current, { zoomControl: false, attributionControl: true, worldCopyJump: true });
      lib.control.zoom({ position: "bottomright" }).addTo(m);
      // fit before adding vectors: Leaflet cannot clip vector layers without a view
      m.fitBounds(lib.geoJSON(lake.flowpath).getBounds().pad(0.08));
      lib.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 18, attribution: "Imagery © Esri · Sentinel © ESA Copernicus · DEM © Copernicus" }).addTo(m);
      lib.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 18, opacity: 0.7 }).addTo(m);

      const g = lib.layerGroup().addTo(m);
      lib.geoJSON(lake.flowpath, { style: { color: "#ff7a3d", weight: 6, opacity: 0.18 } }).addTo(g);
      lib.geoJSON(lake.flowpath, { style: { color: "#ff7a3d", weight: 2.5, opacity: 0.95, dashArray: "8 6" } }).addTo(g);
      lake.eta.forEach((p) => {
        lib.circleMarker([p.lat, p.lon], { radius: 7, color: "#ff7a3d", weight: 2, fillColor: "#05090f", fillOpacity: 1 })
          .bindTooltip(`<b>${p.name}</b><br/>${p.river_km} km downriver<br/>water in <b>${p.eta_min}–${p.eta_max} min</b>`, { className: "jp-tip", direction: "top", offset: [0, -6] })
          .addTo(g);
      });
      const [lon, lat] = lake.lake.seed;
      lib.marker([lat, lon], {
        icon: lib.divIcon({ className: "", iconSize: [18, 18], html: `<span style="position:relative;display:block;width:18px;height:18px"><span class="pulse-ring" style="position:absolute;inset:0;border-radius:99px;background:#4fe3f0"></span><span style="position:absolute;inset:5px;border-radius:99px;background:#4fe3f0;box-shadow:0 0 12px #4fe3f0"></span></span>` }),
      }).bindTooltip(`<b>${lake.lake.name}</b><br/>watched lake`, { className: "jp-tip", direction: "top" }).addTo(g);
      watched.current = g;
      scene.current = lib.layerGroup().addTo(m);
      areaLayer.current = lib.layerGroup().addTo(m);
      map.current = m;
      setReady(true);
      onReady({
        center: () => { const c = m.getCenter(); return [c.lat, c.lng]; },
        flyTo: (la, lo, z = 13) => m.flyTo([la, lo], z, { duration: 1.4 }),
        showPath: () => m.flyToBounds(lib.geoJSON(lake.flowpath).getBounds().pad(0.08), { duration: 1.4 }),
      });
    })();
    return () => { alive = false; map.current?.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // scene overlay + outline for the selected year
  useEffect(() => {
    const lib = L.current, g = scene.current, w = watched.current, m = map.current;
    if (!lib || !g || !w || !m) return;
    g.clearLayers();
    if (showWatched) {
      if (!m.hasLayer(w)) w.addTo(m);
      const s = lake.series[sceneIdx];
      lib.imageOverlay(sceneUrl(s), s.image_bounds, { opacity: 0.95 }).addTo(g);
      lib.geoJSON(s.outline, { style: { color: s.after_burst ? "#ff7a3d" : "#4fe3f0", weight: 2, fillOpacity: 0.12 } }).addTo(g);
    } else if (m.hasLayer(w)) {
      m.removeLayer(w);
    }
  }, [lake, sceneIdx, showWatched, ready]);

  // area screening results
  useEffect(() => {
    const lib = L.current, g = areaLayer.current, m = map.current;
    if (!lib || !g || !m) return;
    g.clearLayers();
    lakeLayers.current = {};
    if (!area) return;
    const [w, s, e, n] = area.box;
    lib.rectangle([[s, w], [n, e]], { color: "#4fe3f0", weight: 1, dashArray: "4 6", fill: false, opacity: 0.7 }).addTo(g);
    area.lakes.forEach((lk) => {
      const c = CLASS_COLOR[lk.class];
      const layer = lib.geoJSON(lk.outline, { style: { color: c, weight: lk.class === "stable" ? 1.5 : 2.5, fillColor: c, fillOpacity: lk.class === "stable" ? 0.12 : 0.3 } })
        .bindTooltip(`<b>${lk.id} · ${lk.class.toUpperCase()}</b> ${lk.class !== "stable" ? `· score ${lk.score}` : ""}<br/>${lk.area_km2} km² · ${lk.elevation_m} m${lk.growth_pct !== null ? ` · ${lk.growth_pct > 0 ? "+" : ""}${lk.growth_pct}%` : lk.new_lake ? " · new lake" : ""}`, { className: "jp-tip", sticky: true })
        .on("click", () => onSelect(lk.id))
        .addTo(g);
      lakeLayers.current[lk.id] = layer;
    });
    m.flyToBounds([[s, w], [n, e]], { duration: 1.4, padding: [30, 30] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area, ready]);

  // highlight the selected lake
  useEffect(() => {
    Object.entries(lakeLayers.current).forEach(([id, layer]) => {
      const lk = area?.lakes.find((x) => x.id === id);
      if (!lk) return;
      layer.setStyle({ weight: id === selected ? 4 : lk.class === "stable" ? 1.5 : 2.5, color: id === selected ? "#ffffff" : CLASS_COLOR[lk.class] });
      if (id === selected) map.current?.flyToBounds(layer.getBounds().pad(1.2), { duration: 1, maxZoom: 15 });
    });
  }, [selected, area, ready]);

  return <div ref={el} className="absolute inset-0" />;
}
