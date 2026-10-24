import type { Metadata } from "next";
import { Console } from "@/components/console/Console";

export const metadata: Metadata = { title: "Console · Jheel Prahari" };

export default function ConsolePage() {
  return <Console />;
}
