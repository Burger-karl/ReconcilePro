"use client";

/**
 * The app's sidebar in the CEK style (DECISIONS D-71, replacing layout C's icon rail from D-50): near-black,
 * with labels, grouped like CEK's footer columns, and the current screen marked by an orange bar and tint.
 * Built on shadcn's Sidebar: it can still collapse to icons on desktop, and is a slide-out sheet on phones.
 */

import { FileText, Inbox, LayoutDashboard, Landmark, ScrollText, Settings, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";

import { UserMenu } from "@/components/app-shell/user-menu";
import { Logo } from "@/components/brand/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { API, type Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

const GROUPS = [
  {
    label: "Menu",
    items: [
      { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
      { href: "/match", label: "Match payments", icon: Inbox },
      { href: "/invoices", label: "Invoices", icon: FileText },
      { href: "/customers", label: "Customers", icon: Users },
      { href: "/statements", label: "Statements", icon: Landmark },
    ],
  },
  {
    label: "Records",
    items: [
      { href: "/audit", label: "Audit log", icon: ScrollText },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
] as const;

export function AppSidebar() {
  const pathname = usePathname();
  // The count on "Match payments" comes from the dashboard summary (backend D-48). SWR shares this request
  // with the Overview screen and refreshes it when the window regains focus.
  const { data: summary } = useSWR<Schemas["Summary"]>(`${API}/dashboard/summary`);
  const needsReview = summary?.needs_review_count ?? 0;

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 pt-5 pb-3 group-data-[collapsible=icon]:px-2">
        <Logo href="/dashboard" onDark size={34} className="group-data-[collapsible=icon]:[&>span:last-child]:hidden" />
      </SidebarHeader>

      <SidebarContent>
        {GROUPS.map((group) => (
          <SidebarGroup key={group.label}>
            {/* Small caps labels, like the column headings in CEK's footer. */}
            <SidebarGroupLabel className="font-nav text-[11px] tracking-[0.15em] text-sidebar-foreground/60 uppercase">
              {group.label}
            </SidebarGroupLabel>
            <SidebarMenu className="gap-1">
              {group.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const badge = item.href === "/match" && needsReview > 0 ? needsReview : null;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={item.label}
                      size="lg"
                      className={cn(
                        "relative h-11 font-nav text-[15px] transition-colors",
                        // The current screen: an orange bar on the left and a fading orange tint (CEK accent).
                        active
                          ? "bg-linear-to-r from-primary/25 to-transparent text-white before:absolute before:inset-y-2 before:-left-2 before:w-1 before:rounded-r before:bg-primary [&>svg]:text-primary"
                          : "hover:bg-white/5 hover:text-white",
                      )}
                    >
                      <Link href={item.href} aria-current={active ? "page" : undefined}>
                        <item.icon aria-hidden />
                        <span>{item.label}</span>
                      </Link>
                    </SidebarMenuButton>
                    {badge !== null && (
                      // The number is in the text too, so colour is not the only signal (MASTER.md §8).
                      <SidebarMenuBadge
                        className="top-3 rounded-full bg-primary px-2 text-xs font-bold text-primary-foreground tabular-nums peer-hover/menu-button:text-primary-foreground peer-data-active/menu-button:text-primary-foreground"
                        aria-label={`${badge} payments need review`}
                      >
                        {badge > 99 ? "99+" : badge}
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="p-3">
        <UserMenu />
      </SidebarFooter>
    </Sidebar>
  );
}
