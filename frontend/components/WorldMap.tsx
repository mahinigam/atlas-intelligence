"use client";

import { useEffect, useEffectEvent, useRef } from "react";
import maplibregl, { FillLayerSpecification, Map } from "maplibre-gl";

type WorldMapProps = {
  selectedCountryCode: string;
  sentimentColor: string;
  onCountrySelect: (countryCode: string, countryName: string) => void;
};

const countryLayerId = "countries-fill";
const selectedLayerId = "countries-selected";

export function WorldMap({ selectedCountryCode, sentimentColor, onCountrySelect }: WorldMapProps) {
  const mapRef = useRef<Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const handleCountrySelect = useEffectEvent(onCountrySelect);
  const pendingVisualStateRef = useRef<{ code: string; color: string }>({
    code: selectedCountryCode,
    color: sentimentColor,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }

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
              "background-color": "#e9dccb",
            },
          },
          {
            id: countryLayerId,
            type: "fill",
            source: "countries",
            "source-layer": "countries",
            paint: {
              "fill-color": "#a7b7b3",
              "fill-opacity": 0.78,
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
              "fill-extrusion-height": 600000,
              "fill-extrusion-base": 0,
              "fill-extrusion-opacity": 0.88,
            },
          },
          {
            id: "country-borders",
            type: "line",
            source: "countries",
            "source-layer": "countries",
            paint: {
              "line-color": "#f9f5eb",
              "line-width": 1.1,
              "line-opacity": 0.85,
            },
          },
        ],
      },
      center: [12, 24],
      zoom: 1.35,
      minZoom: 1.1,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

    map.on("load", () => {
      const nextState = pendingVisualStateRef.current;
      map.setFilter(selectedLayerId, ["==", ["get", "iso_a3"], nextState.code]);
      map.setPaintProperty(selectedLayerId, "fill-extrusion-color", nextState.color);
    });

    map.on("click", countryLayerId, (event) => {
      const feature = event.features?.[0];
      const countryCode = feature?.properties?.iso_a3;
      const countryName = feature?.properties?.name ?? countryCode;

      if (typeof countryCode === "string") {
        handleCountrySelect(countryCode, String(countryName));
      }
    });

    map.on("mouseenter", countryLayerId, () => {
      map.getCanvas().style.cursor = "pointer";
    });

    map.on("mouseleave", countryLayerId, () => {
      map.getCanvas().style.cursor = "";
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

    if (!map || !map.isStyleLoaded()) {
      return;
    }

    map.setFilter(selectedLayerId, ["==", ["get", "iso_a3"], selectedCountryCode]);
    map.setPaintProperty(selectedLayerId, "fill-extrusion-color", sentimentColor);
  }, [selectedCountryCode, sentimentColor]);

  return (
    <div className="relative overflow-hidden rounded-[34px]">
      <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.18),transparent_34%),linear-gradient(180deg,transparent,rgba(23,49,58,0.08))]" />
      <div ref={containerRef} className="h-[560px] w-full rounded-[34px]" />
    </div>
  );
}
