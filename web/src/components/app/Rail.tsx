import {
  Command as CommandIcon,
  Database,
  FolderOpen,
  HelpCircle,
  Languages,
  LogIn,
  LogOut,
  MessagesSquare,
  Moon,
  Plus,
  SlidersHorizontal,
  Sun,
} from "lucide-react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useCreateConversation, useMe, useMeta } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { queryClient, queryKeys } from "@/lib/query";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui";

function RailButton({
  label,
  children,
  onClick,
  asChild = false,
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
  asChild?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {asChild ? (
          children
        ) : (
          <Button
            variant="ghost"
            size="icon-lg"
            aria-label={label}
            onClick={onClick}
            className="text-muted"
          >
            {children}
          </Button>
        )}
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

function NavRailLink({
  to,
  label,
  icon,
}: {
  to: string;
  label: string;
  icon: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <NavLink
          to={to}
          aria-label={label}
          className={({ isActive }) =>
            cn(
              "inline-flex h-10 w-10 items-center justify-center rounded-md text-muted transition-colors",
              "hover:bg-elevated hover:text-fg",
              isActive ? "bg-elevated text-accent" : "",
            )
          }
        >
          {icon}
        </NavLink>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

export function Rail() {
  const t = useT();
  const navigate = useNavigate();
  const theme = useUiStore((state) => state.theme);
  const setTheme = useUiStore((state) => state.setTheme);
  const lang = useUiStore((state) => state.lang);
  const setLang = useUiStore((state) => state.setLang);
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const isDark = theme === "dark" || (theme === "system" && systemDark);

  const { data: meta } = useMeta();
  const { data: me } = useMe();
  const createConversation = useCreateConversation();

  const features = meta?.features;
  const user = me?.user ?? null;

  const newChat = async () => {
    const summary = await createConversation.mutateAsync();
    toast.success(t("toast.created"));
    navigate(`/chat/${summary.id}`);
  };

  const logout = async () => {
    await api.logout();
    queryClient.setQueryData(queryKeys.me, { user: null });
    void queryClient.invalidateQueries();
    toast.success(t("toast.loggedOut"));
    navigate("/login");
  };

  return (
    <nav
      aria-label={t("app.name")}
      className="flex h-full w-14 shrink-0 flex-col items-center gap-1 border-r border-border bg-panel py-3"
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <Link
            to="/chat"
            aria-label={t("app.name")}
            className="mb-2 inline-flex h-9 w-9 items-center justify-center rounded-md bg-accent text-base font-bold text-accent-fg"
          >
            c
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">{t("app.tagline")}</TooltipContent>
      </Tooltip>

      <RailButton label={t("rail.newChat")} onClick={() => void newChat()}>
        <Plus className="h-5 w-5" aria-hidden="true" />
      </RailButton>

      <div className="my-1 h-px w-6 bg-border" />

      <NavRailLink
        to="/chat"
        label={t("nav.chat")}
        icon={<MessagesSquare className="h-5 w-5" aria-hidden="true" />}
      />
      <NavRailLink
        to="/files"
        label={t("nav.files")}
        icon={<FolderOpen className="h-5 w-5" aria-hidden="true" />}
      />
      <NavRailLink
        to="/resources"
        label={t("nav.resources")}
        icon={<Database className="h-5 w-5" aria-hidden="true" />}
      />
      <NavRailLink
        to="/settings"
        label={t("nav.settings")}
        icon={<SlidersHorizontal className="h-5 w-5" aria-hidden="true" />}
      />
      <NavRailLink
        to="/help"
        label={t("nav.help")}
        icon={<HelpCircle className="h-5 w-5" aria-hidden="true" />}
      />

      <div className="mt-auto flex flex-col items-center gap-1">
        <RailButton label={t("rail.command")} onClick={() => setCommandOpen(true)}>
          <CommandIcon className="h-4 w-4" aria-hidden="true" />
        </RailButton>

        <RailButton
          label={t("rail.theme")}
          onClick={() => setTheme(isDark ? "light" : "dark")}
        >
          {isDark ? (
            <Sun className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Moon className="h-5 w-5" aria-hidden="true" />
          )}
        </RailButton>

        <RailButton
          label={t("rail.language")}
          onClick={() => setLang(lang === "en" ? "zh" : "en")}
        >
          <Languages className="h-5 w-5" aria-hidden="true" />
        </RailButton>

        {features?.user_management ? (
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-lg"
                    aria-label={t("rail.user")}
                    className="text-muted"
                  >
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-accent/15 text-2xs font-semibold text-accent">
                      {(user?.username ?? "?").slice(0, 1).toUpperCase()}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="right">{t("rail.user")}</TooltipContent>
            </Tooltip>
            <DropdownMenuContent side="right" align="end">
              <DropdownMenuLabel>{user?.username ?? t("rail.login")}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => window.open("/legacy", "_blank")}>
                <LogIn className="h-4 w-4" aria-hidden="true" />
                {t("rail.legacy")}
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => void logout()}>
                <LogOut className="h-4 w-4" aria-hidden="true" />
                {t("rail.logout")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <RailButton label={t("rail.legacy")} asChild>
            <a
              href="/legacy"
              target="_blank"
              rel="noreferrer"
              aria-label={t("rail.legacy")}
              className="inline-flex h-10 w-10 items-center justify-center rounded-md text-muted transition-colors hover:bg-elevated hover:text-fg"
            >
              <SlidersHorizontal className="h-5 w-5" aria-hidden="true" />
            </a>
          </RailButton>
        )}
      </div>
    </nav>
  );
}
