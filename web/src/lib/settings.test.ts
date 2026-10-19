import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  DEFAULT_CHOICE_VALUE,
  changedSettings,
  fromSelectValue,
  isLongText,
  isSameValue,
  mergeSettings,
  parseNumberInput,
  schemaDefaults,
  settingKeys,
  toSelectValue,
} from "./settings.ts";
import type { SettingsSchema } from "./types.ts";

const SCHEMA: SettingsSchema = {
  groups: [
    {
      id: "application",
      label: "General",
      items: [
        { key: "application.use_llm", label: "LLM", type: "dropdown", choices: [], value: "" },
        { key: "application.temperature", label: "Temperature", type: "number", value: 0.7 },
      ],
    },
    {
      id: "reasoning",
      label: "Reasoning",
      items: [
        { key: "reasoning.use", label: "Mode", type: "radio", choices: [], value: "simple" },
        {
          key: "reasoning.options.simple.tools",
          label: "Tools",
          type: "checkboxgroup",
          choices: [],
          value: ["Search"],
        },
        {
          key: "reasoning.options.simple.system_prompt",
          label: "Prompt",
          type: "text",
          value: "You are a question answering system.",
        },
      ],
    },
  ],
};

describe("the empty choice round-trip", () => {
  it("maps the backend's empty string onto a non-empty Select value", () => {
    assert.equal(toSelectValue(""), DEFAULT_CHOICE_VALUE);
    assert.equal(toSelectValue(null), DEFAULT_CHOICE_VALUE);
    assert.equal(fromSelectValue(DEFAULT_CHOICE_VALUE), "");
  });

  it("keeps ordinary values unchanged", () => {
    assert.equal(toSelectValue("deepseek"), "deepseek");
    assert.equal(fromSelectValue("deepseek"), "deepseek");
    assert.equal(toSelectValue(0), "0");
  });
});

describe("schema defaults and merging", () => {
  it("collects one default per key", () => {
    assert.deepEqual(schemaDefaults(SCHEMA), {
      "application.use_llm": "",
      "application.temperature": 0.7,
      "reasoning.use": "simple",
      "reasoning.options.simple.tools": ["Search"],
      "reasoning.options.simple.system_prompt":
        "You are a question answering system.",
    });
  });

  it("lets stored values win and keeps schema-only keys", () => {
    assert.deepEqual(
      mergeSettings(SCHEMA, {
        "application.temperature": 0.2,
        "reasoning.use": "complex",
      }),
      {
        "application.use_llm": "",
        "application.temperature": 0.2,
        "reasoning.use": "complex",
        "reasoning.options.simple.tools": ["Search"],
        "reasoning.options.simple.system_prompt":
          "You are a question answering system.",
      },
    );
  });

  it("flattens keys in form order", () => {
    assert.deepEqual(settingKeys(SCHEMA).slice(0, 2), [
      "application.use_llm",
      "application.temperature",
    ]);
    assert.equal(settingKeys(undefined).length, 0);
  });
});

describe("dirty tracking", () => {
  it("compares arrays by content, not by reference", () => {
    assert.equal(isSameValue(["a", "b"], ["a", "b"]), true);
    assert.equal(isSameValue(["a"], ["a", "b"]), false);
    assert.equal(isSameValue(1, 1), true);
  });

  it("sends only the keys that changed", () => {
    const initial = mergeSettings(SCHEMA, {});
    const current = {
      ...initial,
      "application.temperature": 0.2,
      "reasoning.options.simple.tools": ["Search", "LLM"],
    };

    assert.deepEqual(changedSettings(initial, current, settingKeys(SCHEMA)), {
      "application.temperature": 0.2,
      "reasoning.options.simple.tools": ["Search", "LLM"],
    });
    assert.deepEqual(changedSettings(initial, { ...initial }, settingKeys(SCHEMA)), {});
  });
});

describe("field heuristics", () => {
  it("treats prompt-like and long values as textareas", () => {
    assert.equal(
      isLongText({
        key: "reasoning.options.simple.system_prompt",
        label: "Prompt",
        type: "text",
        value: "short",
      }),
      true,
    );
    assert.equal(
      isLongText({
        key: "reasoning.options.simple.trigger_context",
        label: "Context",
        type: "number",
        value: 150,
      }),
      false,
    );
    assert.equal(
      isLongText({ key: "x", label: "X", type: "text", value: "a".repeat(120) }),
      true,
    );
  });

  it("rejects empty and non-numeric number inputs", () => {
    assert.equal(parseNumberInput("42"), 42);
    assert.equal(parseNumberInput(" 0.5 "), 0.5);
    assert.equal(parseNumberInput(""), null);
    assert.equal(parseNumberInput("abc"), null);
  });
});
