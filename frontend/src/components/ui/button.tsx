import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 disabled:pointer-events-none disabled:opacity-50", {
  variants: {
    variant: {
      default: "bg-[#426a8a] text-white hover:bg-[#355b79]",
      outline: "border border-[#dddeda] bg-white text-[#405368] hover:bg-[#f4f6f6]",
      ghost: "text-[#526476] hover:bg-[#eff3f5]",
      destructive: "border border-[#e8c9c2] bg-[#fcf3f0] text-[#a34d3e] hover:bg-[#f6e7e2]",
    },
    size: { default: "h-10 px-4", sm: "h-8 px-3 text-xs", icon: "h-9 w-9" },
  }, defaultVariants: { variant: "default", size: "default" },
});

export function Button({ className, variant, size, type = "button", ...props }: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

