"use client";

import { memo, useEffect, useEffectEvent, useRef } from "react";
import * as maptilersdk from "@maptiler/sdk";
import { FilterSpecification, StyleSpecification } from "maplibre-gl";

type WorldMapProps = {
  selectedCountryCode: string;
  sentimentColor: string;
  onCountrySelect: (countryCode: string, countryName: string) => void;
};

const countryLayerId = "countries-fill";
const selectedLayerId = "countries-selected";
const glowLayerId = "countries-glow-border";
const countriesSourceId = "countries";

const fallbackStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: {
        "background-color": "#dcd0bc",
      },
    },
  ],
};

function getCountryCodeFilter(countryCode: string): FilterSpecification {
  return [
    "all",
    ["==", ["get", "level"], 0],
    [
      "==",
      [
        "coalesce",
        ["get", "iso_a3"],
        ["get", "ISO_A3"],
        ["get", "ADM0_A3"],
        ["get", "adm0_a3"],
        ["get", "ISO3166-1-Alpha-3"],
      ],
      countryCode,
    ]
  ] as FilterSpecification;
}

function getCountryName(properties: Record<string, unknown> | undefined, fallbackCode: string) {
  return String(
    properties?.name ??
      properties?.NAME ??
      properties?.name_en ??
      properties?.ADMIN ??
      fallbackCode
  );
}

function ensureCountryLayers(map: maptilersdk.Map, selectedCountryCode: string, sentimentColor: string) {
  if (!map.getSource(countriesSourceId)) {
    map.addSource(countriesSourceId, {
      type: "vector",
      url: `https://api.maptiler.com/tiles/countries/tiles.json?key=${maptilersdk.config.apiKey}`
    });
  }

  if (!map.getLayer(countryLayerId)) {
    map.addLayer({
      id: countryLayerId,
      type: "fill",
      source: countriesSourceId,
      "source-layer": "administrative",
      filter: ["==", ["get", "level"], 0],
      paint: {
        "fill-color": "#8d9c99",
        "fill-opacity": 0.55,
      },
    });
  }

  if (!map.getLayer(selectedLayerId)) {
    map.addLayer({
      id: selectedLayerId,
      type: "fill",
      source: countriesSourceId,
      "source-layer": "administrative",
      filter: getCountryCodeFilter(selectedCountryCode),
      paint: {
        "fill-color": sentimentColor,
        "fill-opacity": 0.34,
      },
    });
  }

  if (!map.getLayer(glowLayerId)) {
    map.addLayer({
      id: glowLayerId,
      type: "line",
      source: countriesSourceId,
      "source-layer": "administrative",
      filter: getCountryCodeFilter(selectedCountryCode),
      paint: {
        "line-color": sentimentColor,
        "line-width": 2.5,
        "line-opacity": 0.95,
      },
    });
  }

  if (!map.getLayer("country-borders")) {
    map.addLayer({
      id: "country-borders",
      type: "line",
      source: countriesSourceId,
      "source-layer": "administrative",
      filter: ["==", ["get", "level"], 0],
      paint: {
        "line-color": "#f2ebd9",
        "line-width": 1.2,
        "line-opacity": 0.6,
      },
    });
  }
}

export const WorldMap = memo(function WorldMap({
  selectedCountryCode,
  sentimentColor,
  onCountrySelect,
}: WorldMapProps) {
  const mapRef = useRef<maptilersdk.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const handleCountrySelect = useEffectEvent(onCountrySelect);
  const pendingVisualStateRef = useRef<{ code: string; color: string }>({
    code: selectedCountryCode,
    color: sentimentColor,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const apiKey = process.env.NEXT_PUBLIC_MAPTILER_API_KEY;
    if (apiKey) maptilersdk.config.apiKey = apiKey;

    const map = new maptilersdk.Map({
      container: containerRef.current,
      style: maptilersdk.MapStyle.BACKDROP,
      center: [78.9629, 22.5937],
      zoom: 2.2,
      minZoom: 1.2,
      maxZoom: 6,
      pitch: 34,
      maxPitch: 48,
      renderWorldCopies: true,
    });

    map.addControl(new maptilersdk.NavigationControl({ visualizePitch: true }), "top-right");

    map.on("load", () => {
      ensureCountryLayers(map, selectedCountryCode, sentimentColor);
      const nextState = pendingVisualStateRef.current;
      const matchExpression = getCountryCodeFilter(nextState.code);
      map.setFilter(selectedLayerId, matchExpression);
      map.setPaintProperty(selectedLayerId, "fill-color", nextState.color);

      map.setFilter(glowLayerId, matchExpression);
      map.setPaintProperty(glowLayerId, "line-color", nextState.color);
    });

    map.on("click", countryLayerId, (event) => {
      const props = event.features?.[0]?.properties as Record<string, unknown> | undefined;
      const countryCode =
        props?.iso_a3 ??
        props?.ISO_A3 ??
        props?.ADM0_A3 ??
        props?.adm0_a3 ??
        props?.["ISO3166-1-Alpha-3"];

      if (typeof countryCode === "string") {
        if (countryCode === pendingVisualStateRef.current.code) {
          return;
        }

        handleCountrySelect(countryCode, getCountryName(props, countryCode));

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

    const tooltipPopup = new maptilersdk.Popup({
      closeButton: false,
      closeOnClick: false,
      className: "atlas-tooltip",
    });

    map.on("mousemove", countryLayerId, (e) => {
      if (e.features && e.features.length > 0) {
        map.getCanvas().style.cursor = "pointer";
        const props = e.features[0].properties as Record<string, unknown> | undefined;
        const fallbackCode = String(
          props?.iso_a3 ??
            props?.ISO_A3 ??
            props?.ADM0_A3 ??
            props?.adm0_a3 ??
            props?.["ISO3166-1-Alpha-3"] ??
            "Unknown Region"
        );
        const name = getCountryName(props, fallbackCode);

        if (name) {
          tooltipPopup
            .setLngLat(e.lngLat)
            .setHTML(`<div style="background-color: rgba(23, 49, 58, 0.95); border: 1px solid rgba(23, 49, 58, 0.1); padding: 6px 10px; border-radius: 8px;"><span class="data-font text-[11px] font-semibold tracking-wider text-[#dcd0bc]">${name}</span></div>`)
            .addTo(map);
        }
      }
    });

    map.on("mouseleave", countryLayerId, () => {
      map.getCanvas().style.cursor = "";
      tooltipPopup.remove();
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

    ensureCountryLayers(map, selectedCountryCode, sentimentColor);
    const matchExpression = getCountryCodeFilter(selectedCountryCode);

    map.setFilter(selectedLayerId, matchExpression);
    map.setPaintProperty(selectedLayerId, "fill-color", sentimentColor);

    map.setFilter(glowLayerId, matchExpression);
    map.setPaintProperty(glowLayerId, "line-color", sentimentColor);
  }, [selectedCountryCode, sentimentColor]);

  return (
    <div className="relative overflow-hidden rounded-[calc(var(--radius-xl)-6px)] border border-[rgba(23,49,58,0.08)]">
      {/* Premium Inner Shadow Overlay */}
      <div className="pointer-events-none absolute inset-0 z-10 shadow-[inset_6px_6px_20px_rgba(158,138,114,0.3),inset_-6px_-6px_20px_rgba(255,255,255,0.7)]" />
      
      {/* Map Container */}
      <div ref={containerRef} className="h-[520px] w-full bg-[var(--bg-deep)] md:h-[600px]" />
    </div>
  );
});
