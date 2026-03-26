"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";
import maplibregl, { FillLayerSpecification, Map } from "maplibre-gl";

type WorldMapProps = {
  selectedCountryCode: string;
  sentimentColor: string;
  onCountrySelect: (countryCode: string, countryName: string) => void;
};

const countryLayerId = "countries-fill";
const selectedLayerId = "countries-selected";
const glowLayerId = "countries-glow-border";

export function WorldMap({ selectedCountryCode, sentimentColor, onCountrySelect }: WorldMapProps) {
  const mapRef = useRef<Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hoveredCountry, setHoveredCountry] = useState<{ name: string; x: number; y: number } | null>(null);

  const handleCountrySelect = useEffectEvent(onCountrySelect);
  const pendingVisualStateRef = useRef<{ code: string; color: string }>({
    code: selectedCountryCode,
    color: sentimentColor,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          countries: {
            type: "vector",
            tiles: ["https://demotiles.maplibre.org/tiles/{z}/{x}/{y}.pbf"],
          },
        },
        layers: [
          {
            id: "background",
            type: "background",
            paint: {
              "background-color": "#dcd0bc",
            },
          },
          {
            id: countryLayerId,
            type: "fill",
            source: "countries",
            "source-layer": "countries",
            paint: {
              "fill-color": "#8d9c99",
              "fill-opacity": 0.55,
            },
          } satisfies FillLayerSpecification,
          {
            id: selectedLayerId,
            type: "fill-extrusion",
            source: "countries",
            "source-layer": "countries",
            filter: ["==", ["get", "iso_a3"], selectedCountryCode],
            paint: {
              "fill-extrusion-color": sentimentColor,
              "fill-extrusion-height": 1200000,
              "fill-extrusion-base": 0,
              "fill-extrusion-opacity": 0.95,
            },
          },
          {
            id: glowLayerId,
            type: "line",
            source: "countries",
            "source-layer": "countries",
            filter: ["==", ["get", "iso_a3"], selectedCountryCode],
            paint: {
              "line-color": sentimentColor,
              "line-width": 3,
              "line-opacity": 0.8,
              "line-blur": 4,
            },
          },
          {
            id: "country-borders",
            type: "line",
            source: "countries",
            "source-layer": "countries",
            paint: {
              "line-color": "#f2ebd9",
              "line-width": 1.2,
              "line-opacity": 0.6,
            },
          },
        ],
      },
      center: [12, 24],
      zoom: 1.4,
      minZoom: 1.2,
      maxZoom: 6,
      pitch: 45, // 3D globe perspective
      maxBounds: [[-180, -85], [180, 85]], // Prevent over-scrolling
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

    map.on("load", () => {
      const nextState = pendingVisualStateRef.current;
      map.setFilter(selectedLayerId, ["==", ["get", "iso_a3"], nextState.code]);
      map.setPaintProperty(selectedLayerId, "fill-extrusion-color", nextState.color);
      
      map.setFilter(glowLayerId, ["==", ["get", "iso_a3"], nextState.code]);
      map.setPaintProperty(glowLayerId, "line-color", nextState.color);
    });

    map.on("click", countryLayerId, (event) => {
      const feature = event.features?.[0];
      const countryCode = feature?.properties?.iso_a3;
      const countryName = feature?.properties?.name ?? countryCode;

      if (typeof countryCode === "string") {
        handleCountrySelect(countryCode, String(countryName));
        
        // Smooth fly to the clicked country
        const coordinates = event.lngLat;
        map.flyTo({
          center: coordinates,
          zoom: Math.max(map.getZoom(), 2.5),
          speed: 0.8,
          curve: 1.2,
          easing: (t) => t * (2 - t),
          essential: true,
        });
      }
    });

    map.on("mousemove", countryLayerId, (e) => {
      if (e.features && e.features.length > 0) {
        map.getCanvas().style.cursor = "pointer";
        const name = e.features[0].properties?.name;
        if (name) {
          setHoveredCountry({
            name: String(name),
            x: e.point.x,
            y: e.point.y,
          });
        }
      }
    });

    map.on("mouseleave", countryLayerId, () => {
      map.getCanvas().style.cursor = "";
      setHoveredCountry(null);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [handleCountrySelect]);

  useEffect(() => {
    const map = mapRef.current;
    pendingVisualStateRef.current = { code: selectedCountryCode, color: sentimentColor };

    if (!map || !map.isStyleLoaded()) return;

    map.setFilter(selectedLayerId, ["==", ["get", "iso_a3"], selectedCountryCode]);
    map.setPaintProperty(selectedLayerId, "fill-extrusion-color", sentimentColor);

    map.setFilter(glowLayerId, ["==", ["get", "iso_a3"], selectedCountryCode]);
    map.setPaintProperty(glowLayerId, "line-color", sentimentColor);
  }, [selectedCountryCode, sentimentColor]);

  return (
    <div className="relative overflow-hidden rounded-[calc(var(--radius-xl)-6px)] border border-[rgba(23,49,58,0.08)]">
      {/* Premium Inner Shadow Overlay */}
      <div className="pointer-events-none absolute inset-0 z-10 shadow-[inset_6px_6px_20px_rgba(158,138,114,0.3),inset_-6px_-6px_20px_rgba(255,255,255,0.7)]" />
      
      {/* Map Container */}
      <div ref={containerRef} className="h-[520px] w-full bg-[var(--bg-deep)] md:h-[600px]" />

      {/* Custom Hover Tooltip directly in DOM for better Framer Motion/CSS interop */}
      {hoveredCountry && (
        <div
          className="pointer-events-none absolute z-20 rounded-[14px] border border-[var(--border)] bg-[rgba(240,230,214,0.92)] px-3 py-1.5 shadow-[var(--shadow-outer-sm)] backdrop-blur-md transition-all duration-75"
          style={{
            left: hoveredCountry.x + 15,
            top: hoveredCountry.y + 15,
          }}
        >
          <span className="data-font text-xs font-semibold tracking-wider text-[var(--text)]">
            {hoveredCountry.name}
          </span>
        </div>
      )}
    </div>
  );
}
