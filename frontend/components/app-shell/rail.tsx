"use client";

/**
 * Layout C's narrow icon rail (DECISIONS D-50), built on shadcn's Sidebar in "icon" mode: always collapsed
 * on desktop (icons + tooltips), a slide-out sheet with labels on phones.
 */

import { FileText, Inbox, LayoutDashboard, ScrollText, Settings, Upload, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";

import { LogoMark } from "@/components/brand/logo";

import { UserMenu } from "@/components/app-shell/user-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { API, type Schemas } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/match", label: "Match payments", icon: Inbox },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/statements", label: "Statements", icon: Upload },
  { href: "/audit", label: "Audit log", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Rail() {
  const pathname = usePathname();
  // The amber count on "Match" comes from the dashboard summary (backend D-48). SWR shares this request
  // with the Overview screen and refreshes it when the window regains focus.
  const { data: summary } = useSWR<Schemas["Summary"]>(`${API}/dashboard/summary`);
  const needsReview = summary?.needs_review_count ?? 0;

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="ReconcilePro" size="lg" className="hover:bg-transparent">
              <Link href="/dashboard">
                {/* The owner's logo mark on a white tile: its navy "R" would vanish on the navy rail (D-65). */}
                <LogoMark onDark size={20} />
                <span className="font-semibold text-white">
                  Reconcile<span className="text-emerald-400">Pro</span>
                </span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarMenu className="gap-1 px-2">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const badge = item.href === "/match" && needsReview > 0 ? needsReview : null;
            return (
              <SidebarMenuItem key={item.href} className="relative">
                {/* Active = teal (sidebar-accent token). Hover on the others is a faint white tint, so the
                    current screen always stands out (D-62). */}
                <SidebarMenuButton
                  asChild
                  isActive={active}
                  tooltip={item.label}
                  className={active ? undefined : "transition-colors hover:bg-white/5 hover:text-slate-100"}
                >
                  <Link href={item.href} aria-current={active ? "page" : undefined}>
                    <item.icon aria-hidden />
                    <span>{item.label}</span>
                  </Link>
                </SidebarMenuButton>
                {badge !== null && (
                  // The number is in the text too, so colour is not the only signal (MASTER.md §8).
                  <span
                    className="pointer-events-none absolute -top-1 right-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 text-[10px] font-semibold text-slate-950 tabular-nums"
                    aria-label={`${badge} payments need review`}
                  >
                    {badge > 99 ? "99+" : badge}
                  </span>
                )}
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  );
}
