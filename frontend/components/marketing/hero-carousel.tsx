"use client";

/**
 * The hero's background photos (DECISIONS D-71): a slow crossfade every 6 seconds, with dots to pick one.
 * Decoration only, so the images have alt="" and the dots say which photo they show. Nothing moves for
 * people who ask their system for reduced motion: the first photo just stays.
 */

import Image from "next/image";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const PHOTOS = ["/images/hero-1.jpg", "/images/hero-2.jpg", "/images/hero-3.jpg"];

export function HeroCarousel() {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = setInterval(() => setCurrent((index) => (index + 1) % PHOTOS.length), 6000);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      {PHOTOS.map((src, index) => (
        <Image
          key={src}
          src={src}
          alt=""
          fill
          priority={index === 0}
          sizes="100vw"
          className={cn(
            "-z-20 object-cover transition-[opacity,scale] duration-[1400ms] ease-out motion-reduce:transition-none",
            index === current ? "scale-100 opacity-100" : "scale-105 opacity-0",
          )}
        />
      ))}
      <div className="absolute inset-x-0 bottom-7 z-10 flex justify-center gap-2">
        {PHOTOS.map((src, index) => (
          <button
            key={src}
            type="button"
            aria-label={`Show photo ${index + 1}`}
            aria-current={index === current}
            onClick={() => setCurrent(index)}
            className={cn(
              "h-2.5 rounded-full transition-all",
              index === current ? "w-7 bg-primary" : "w-2.5 bg-white/40 hover:bg-white/70",
            )}
          />
        ))}
      </div>
    </>
  );
}
