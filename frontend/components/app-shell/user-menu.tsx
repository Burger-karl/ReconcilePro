"use client";

import { LogOut, Moon, Sun } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { useAuth } from "@/lib/auth";

/** Bottom of the rail: who is signed in, to which workspace; theme and sign out. */
export function UserMenu() {
  const auth = useAuth();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  if (auth.status !== "signed-in") return null;
  const { user, workspace } = auth.me;
  const initial = (workspace.name.trim()[0] ?? "?").toUpperCase();

  function signOut() {
    auth.signOut();
    router.replace("/login");
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" tooltip={`${workspace.name} · ${user.email}`} aria-label="Account menu">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sidebar-accent text-sm font-semibold text-sidebar-accent-foreground">
                {initial}
              </span>
              <span className="flex min-w-0 flex-col text-left leading-tight">
                <span className="truncate text-sm font-medium text-sidebar-accent-foreground">{workspace.name}</span>
                <span className="truncate text-xs">{user.email}</span>
              </span>
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="end" className="w-60">
            <DropdownMenuLabel className="flex flex-col gap-0.5">
              <span className="truncate">{workspace.name}</span>
              <span className="truncate text-xs font-normal text-muted-foreground">{user.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
              <Sun className="dark:hidden" aria-hidden />
              <Moon className="hidden dark:block" aria-hidden />
              {resolvedTheme === "dark" ? "Light theme" : "Dark theme"}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={signOut}>
              <LogOut aria-hidden />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
