"use client";

import { memo, useEffect, useEffectEvent, useRef } from "react";
import * as maptilersdk from "@maptiler/sdk";
import { StyleSpecification } from "maplibre-gl";
import * as isoCountries from "i18n-iso-countries";
import enLocale from "i18n-iso-countries/langs/en.json";

isoCountries.registerLocale(enLocale);

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

function getCountryName(properties: Record<string, unknown> | undefined, fallbackCode: string) {
  return String(
    properties?.name ??
      properties?.NAME ??
      properties?.name_en ??
      properties?.ADMIN ??
      fallbackCode
  );
}

function ensureCountryLayers(map: maptilersdk.Map) {
  if (!map.getSource(countriesSourceId)) {
    map.addSource(countriesSourceId, {
      type: "vector",
      url: `https://api.maptiler.com/tiles/countries/tiles.json?key=${maptilersdk.config.apiKey}`,
      promoteId: "iso_a2"
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
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          ["feature-state", "color"],
          "rgba(0,0,0,0)"
        ],
        "fill-opacity": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          0.34,
          0
        ]
      },
    });
  }

  if (!map.getLayer(glowLayerId)) {
    map.addLayer({
      id: glowLayerId,
      type: "line",
      source: countriesSourceId,
      "source-layer": "administrative",
      filter: ["==", ["get", "level"], 0],
      paint: {
        "line-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          ["feature-state", "color"],
          "rgba(0,0,0,0)"
        ],
        "line-width": 2.5,
        "line-opacity": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          0.95,
          0
        ]
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
      ensureCountryLayers(map);
      const nextState = pendingVisualStateRef.current;
      const iso2 = isoCountries.alpha3ToAlpha2(nextState.code) || nextState.code;
      map.setFeatureState(
        { source: countriesSourceId, sourceLayer: "administrative", id: iso2 },
        { selected: true, color: nextState.color }
      );
    });

    map.on("click", countryLayerId, (event) => {
      const props = event.features?.[0]?.properties as Record<string, unknown> | undefined;
      const clickedIso2 = props?.iso_a2 ?? props?.ISO_A2;
      const countryCode = clickedIso2 ? isoCountries.alpha2ToAlpha3(String(clickedIso2)) : undefined;

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
        const clickedIso2 = props?.iso_a2 ?? props?.ISO_A2;
        const fallbackCode = clickedIso2 ? (isoCountries.alpha2ToAlpha3(String(clickedIso2)) || String(clickedIso2)) : "Unknown Region";
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
    
    if (!map || !map.isStyleLoaded()) {
      pendingVisualStateRef.current = { code: selectedCountryCode, color: sentimentColor };
      return;
    }

    ensureCountryLayers(map);
    const prevState = pendingVisualStateRef.current;
    const currentIso2 = isoCountries.alpha3ToAlpha2(selectedCountryCode) || selectedCountryCode;
    
    if (prevState.code && prevState.code !== selectedCountryCode) {
      const prevIso2 = isoCountries.alpha3ToAlpha2(prevState.code) || prevState.code;
      map.setFeatureState(
        { source: countriesSourceId, sourceLayer: "administrative", id: prevIso2 },
        { selected: false }
      );
    }

    map.setFeatureState(
      { source: countriesSourceId, sourceLayer: "administrative", id: currentIso2 },
      { selected: true, color: sentimentColor }
    );

    pendingVisualStateRef.current = { code: selectedCountryCode, color: sentimentColor };
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
