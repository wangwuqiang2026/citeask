"""Visual theme of the application.

The look is built from two layers that share one palette:

* this Gradio theme — the variables Gradio's own components are rendered with;
* ``assets/css/tokens.css`` (``--ui-*`` tokens) — what ``assets/css/main.css`` is
  written against.

``primary_hue=colors.blue`` and ``neutral_hue=colors.slate`` map one-to-one onto
the token values (``#2563EB`` is ``blue-600``, ``#F8FAFC`` is ``slate-50``,
``#0A0F1E`` is ``slate-950`` …), so a Gradio widget and a hand-styled panel never
disagree in either mode.

Two deliberate departures from the stock Soft theme:

* the *solid* primary button. The previous gradient could not follow the accent
  colour of the dark theme, and it competed with the wordmark. There is no
  gradient anywhere in the theme any more.
* the font stack is the platform's own sans-serif plus CJK fallbacks — no remote
  web font is requested, so the UI renders correctly without network access and
  Chinese text is not forced through a Latin-only font.
"""

from typing import Iterable

from gradio.themes import Soft
from gradio.themes.utils import colors, fonts, sizes

err = "rgba(220, 38, 38, 1)"  # red-600 → --ui-danger (light)
err_muted = "rgba(220, 38, 38, 0.75)"
err_dark = "rgba(248, 113, 113, 1)"  # red-400 → --ui-danger (dark)
err_dark_muted = "rgba(248, 113, 113, 0.75)"

#: System font stack mirrored by ``--ui-font-sans`` in tokens.css. Multi-word
#: families go through :class:`fonts.Font` so they are quoted in the CSS.
FONT_SANS = (
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    fonts.Font("Segoe UI"),
    fonts.Font("PingFang SC"),
    fonts.Font("Hiragino Sans GB"),
    fonts.Font("Microsoft YaHei UI"),
    fonts.Font("Microsoft YaHei"),
    fonts.Font("Noto Sans CJK SC"),
    fonts.Font("Source Han Sans SC"),
    "sans-serif",
)

#: Monospace stack mirrored by ``--ui-font-mono``.
FONT_MONO = (
    "ui-monospace",
    "SFMono-Regular",
    fonts.Font("Cascadia Code"),
    "Consolas",
    fonts.Font("Liberation Mono"),
    "monospace",
)


#: Values shared by both modes (layout atoms, borders and the button geometry).
#: Gradio only lets a mode-specific value be overridden through the ``_dark``
#: suffix, so anything identical in both modes belongs here.
common = dict(
    # layout atoms
    layout_gap="*spacing_xl",
    block_label_margin="*spacing_xl",
    block_label_padding="*spacing_xl",
    block_label_shadow="none",
    section_header_text_size="*text_lg",
    # flat panels / solid borders
    block_border_width="1px",
    block_label_border_width="0px",
    block_shadow="none",
    panel_border_width="0px",
    button_border_width="1px",
    input_border_width="1px",
    checkbox_border_width="1px",
    # spacing tokens of the app's own CSS
    shadow_drop="0 1px 2px rgba(15, 23, 42, 0.06)",
    shadow_drop_lg="0 4px 12px rgba(15, 23, 42, 0.08)",
    # buttons: flat, solid, no gradient anywhere
    button_shadow="none",
    button_shadow_active="*shadow_drop",
    button_shadow_hover="none",
    button_small_radius="*radius_md",
    button_large_radius="*radius_md",
    # gradio has no dark variant of the accent colour; the token layer covers the
    # components that need a lighter accent on a dark surface
    color_accent="*primary_600",
)


light_mode = dict(
    # ---- surfaces ----------------------------------------------------------
    # a literal colour, not a hue reference: the contrast guard in
    # ktem_tests/test_ui_theme.py follows var() chains down to a literal value
    background_fill_primary="#ffffff",
    background_fill_secondary="*neutral_100",
    body_background_fill="*neutral_50",
    # ---- text --------------------------------------------------------------
    body_text_color="*neutral_800",
    body_text_color_subdued="*neutral_600",
    # ---- borders -----------------------------------------------------------
    border_color_primary="*neutral_200",
    border_color_accent="*primary_400",
    border_color_accent_subdued="*primary_200",
    # ---- accent & links ----------------------------------------------------
    color_accent_soft="*primary_50",
    link_text_color="*primary_600",
    link_text_color_active="*primary_700",
    link_text_color_visited="*primary_700",
    # ---- blocks ------------------------------------------------------------
    block_background_fill="white",
    block_border_color="*neutral_200",
    block_label_background_fill="white",
    block_label_text_color="*neutral_600",
    block_title_text_color="*neutral_800",
    # ---- inputs ------------------------------------------------------------
    input_background_fill="white",
    input_border_color="*neutral_200",
    input_border_color_focus="*primary_500",
    input_placeholder_color="*neutral_400",
    # ---- checkboxes & radios ----------------------------------------------
    checkbox_background_color="white",
    checkbox_background_color_selected="*primary_600",
    checkbox_border_color="*neutral_300",
    checkbox_border_color_focus="*primary_500",
    checkbox_border_color_selected="*primary_600",
    checkbox_label_background_fill="white",
    checkbox_label_background_fill_selected="*primary_50",
    checkbox_label_border_color="*neutral_200",
    checkbox_label_text_color="*neutral_700",
    checkbox_label_text_color_selected="*neutral_800",
    # ---- feedback ----------------------------------------------------------
    error_background_fill="*neutral_50",
    error_border_color=err,
    error_text_color="*neutral_800",
    error_icon_color=err,
    # ---- tables ------------------------------------------------------------
    table_border_color="*neutral_200",
    table_even_background_fill="white",
    table_odd_background_fill="*neutral_50",
    table_row_focus="*primary_50",
    # ---- misc components ---------------------------------------------------
    slider_color="*primary_600",
    loader_color="*primary_600",
    stat_background_fill="*primary_50",
    # ---- buttons -----------------------------------------------------------
    button_primary_background_fill="*primary_600",
    button_primary_background_fill_hover="*primary_700",
    button_primary_border_color="*primary_600",
    button_primary_border_color_hover="*primary_700",
    button_primary_text_color="*neutral_50",
    button_primary_text_color_hover="*neutral_50",
    button_secondary_background_fill="white",
    button_secondary_background_fill_hover="*neutral_100",
    button_secondary_border_color="*neutral_200",
    button_secondary_border_color_hover="*neutral_300",
    button_secondary_text_color="*neutral_700",
    button_secondary_text_color_hover="*neutral_800",
    button_cancel_background_fill=err,
    button_cancel_background_fill_hover=err_muted,
    button_cancel_border_color=err,
    button_cancel_border_color_hover=err_muted,
    button_cancel_text_color="*neutral_50",
)


dark_mode = dict(
    # ---- surfaces ----------------------------------------------------------
    background_fill_primary_dark="*neutral_900",
    background_fill_secondary_dark="*neutral_800",
    body_background_fill_dark="*neutral_950",
    # ---- text --------------------------------------------------------------
    body_text_color_dark="*neutral_100",
    body_text_color_subdued_dark="*neutral_300",
    # ---- borders -----------------------------------------------------------
    border_color_primary_dark="*neutral_800",
    border_color_accent_dark="*primary_400",
    border_color_accent_subdued_dark="rgba(96, 165, 250, 0.32)",
    # ---- accent & links ----------------------------------------------------
    color_accent_soft_dark="rgba(96, 165, 250, 0.12)",
    link_text_color_dark="*primary_300",
    link_text_color_active_dark="*primary_200",
    link_text_color_visited_dark="*primary_300",
    # ---- blocks ------------------------------------------------------------
    block_background_fill_dark="*neutral_900",
    block_border_color_dark="*neutral_800",
    block_label_background_fill_dark="*neutral_900",
    block_label_text_color_dark="*neutral_300",
    block_title_text_color_dark="*neutral_100",
    # ---- inputs ------------------------------------------------------------
    input_background_fill_dark="*neutral_800",
    input_border_color_dark="*neutral_700",
    input_border_color_focus_dark="*primary_400",
    input_placeholder_color_dark="*neutral_400",
    # ---- checkboxes & radios ----------------------------------------------
    checkbox_background_color_dark="*neutral_800",
    checkbox_background_color_selected_dark="*primary_400",
    checkbox_border_color_dark="*neutral_600",
    checkbox_border_color_focus_dark="*primary_400",
    checkbox_border_color_selected_dark="*primary_400",
    checkbox_label_background_fill_dark="*neutral_800",
    checkbox_label_background_fill_selected_dark="rgba(96, 165, 250, 0.12)",
    checkbox_label_border_color_dark="*neutral_700",
    checkbox_label_text_color_dark="*neutral_200",
    checkbox_label_text_color_selected_dark="*neutral_100",
    # ---- feedback ----------------------------------------------------------
    error_background_fill_dark="rgba(248, 113, 113, 0.12)",
    error_border_color_dark=err_dark,
    error_text_color_dark="*neutral_100",
    error_icon_color_dark=err_dark,
    # ---- tables ------------------------------------------------------------
    table_border_color_dark="*neutral_800",
    table_even_background_fill_dark="*neutral_900",
    table_odd_background_fill_dark="*neutral_800",
    table_row_focus_dark="*neutral_700",
    # ---- misc components ---------------------------------------------------
    slider_color_dark="*primary_400",
    loader_color_dark="*primary_300",
    stat_background_fill_dark="*neutral_800",
    # ---- buttons -----------------------------------------------------------
    button_primary_background_fill_dark="*primary_400",
    button_primary_background_fill_hover_dark="*primary_300",
    button_primary_border_color_dark="*primary_400",
    button_primary_border_color_hover_dark="*primary_300",
    button_primary_text_color_dark="*neutral_950",
    button_primary_text_color_hover_dark="*neutral_950",
    button_secondary_background_fill_dark="*neutral_800",
    button_secondary_background_fill_hover_dark="*neutral_700",
    button_secondary_border_color_dark="*neutral_700",
    button_secondary_border_color_hover_dark="*neutral_600",
    button_secondary_text_color_dark="*neutral_100",
    button_secondary_text_color_hover_dark="*neutral_50",
    button_cancel_background_fill_dark=err_dark,
    button_cancel_background_fill_hover_dark=err_dark_muted,
    button_cancel_border_color_dark=err_dark,
    button_cancel_border_color_hover_dark=err_dark_muted,
    button_cancel_text_color_dark="*neutral_950",
)


class Kotaemon(Soft):
    """
    Default theme of the application.
    """

    def __init__(
        self,
        *,
        primary_hue: colors.Color | str = colors.blue,
        secondary_hue: colors.Color | str = colors.slate,
        neutral_hue: colors.Color | str = colors.slate,
        spacing_size: sizes.Size | str = sizes.spacing_md,
        radius_size: sizes.Size | str = sizes.radius_md,
        text_size: sizes.Size | str = sizes.text_md,
        font: fonts.Font | str | Iterable[fonts.Font | str] = FONT_SANS,
        font_mono: fonts.Font | str | Iterable[fonts.Font | str] = FONT_MONO,
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=font,
            font_mono=font_mono,
        )
        self.name = "citeask"
        super().set(
            **common,
            **dark_mode,
            **light_mode,
        )
