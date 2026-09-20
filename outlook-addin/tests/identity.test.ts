import { describe, expect, it, vi, beforeEach } from "vitest";
import { FakeCurrentMailContextProvider } from "../src/office/FakeContextProvider";
import { IdentityAdapter } from "../src/office/IdentityAdapter";
import type { ProductEmailDetail } from "../src/types/product";

// Mock the API module
vi.mock("../src/api/client", () => ({
  findEmailByMessageId: vi.fn(),
  searchEmailQueue: vi.fn(),
  getEmailDetail: vi.fn(),
}));

import { findEmailByMessageId, searchEmailQueue, getEmailDetail } from "../src/api/client";

const mockFind = vi.mocked(findEmailByMessageId);
const mockSearch = vi.mocked(searchEmailQueue);
const mockDetail = vi.mocked(getEmailDetail);

const fakeDetail = { email: { id: "email-abc" } } as ProductEmailDetail;

describe("FakeCurrentMailContextProvider", () => {
  it("returns ready state with default data", async () => {
    const provider = new FakeCurrentMailContextProvider();
    const ctx = await provider.getContext();
    expect(ctx.state).toBe("ready");
    expect(ctx.item).not.toBeNull();
    expect(ctx.item?.sender).toBe("shipper@example.com");
  });

  it("accepts custom item overrides", async () => {
    const provider = new FakeCurrentMailContextProvider({
      subject: "My custom subject",
      internetMessageId: "<custom@test.com>",
    });
    const ctx = await provider.getContext();
    expect(ctx.item?.subject).toBe("My custom subject");
    expect(ctx.item?.internetMessageId).toBe("<custom@test.com>");
  });

  it("returns unavailable when null is passed", async () => {
    const provider = new FakeCurrentMailContextProvider(null);
    const ctx = await provider.getContext();
    expect(ctx.state).toBe("unavailable");
    expect(ctx.item).toBeNull();
  });

  it("returns error state when error string is passed", async () => {
    const provider = new FakeCurrentMailContextProvider(undefined, "Office not loaded");
    const ctx = await provider.getContext();
    expect(ctx.state).toBe("unavailable");
    expect(ctx.error).toBe("Office not loaded");
  });
});

describe("IdentityAdapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("resolves via internet_message_id when backend finds a match", async () => {
    mockFind.mockResolvedValue(fakeDetail);

    const provider = new FakeCurrentMailContextProvider({
      internetMessageId: "<msg-001@example.com>",
    });
    const adapter = new IdentityAdapter(provider);
    const result = await adapter.resolve();

    expect(result.strategy).toBe("internet_message_id");
    expect(result.confidence).toBe("high");
    expect(result.detail).toBe(fakeDetail);
    expect(result.limitationNote).toBeNull();
  });

  it("falls back to subject search when no message-id match", async () => {
    mockFind.mockResolvedValue(null);
    mockSearch.mockResolvedValue({
      items: [{ id: "email-xyz", subject: "Draft BL check" } as ProductEmailDetail["email"]],
      total: 1,
      skip: 0,
      limit: 10,
    });
    mockDetail.mockResolvedValue({ ...fakeDetail, email: { ...fakeDetail.email, id: "email-xyz" } });

    const provider = new FakeCurrentMailContextProvider({
      internetMessageId: "<nomatch@example.com>",
      subject: "Draft BL check",
    });
    const adapter = new IdentityAdapter(provider);
    const result = await adapter.resolve();

    expect(result.strategy).toBe("subject_search");
    expect(result.confidence).toBe("low");
    expect(result.limitationNote).not.toBeNull();
  });

  it("returns not_resolved when multiple subject matches exist", async () => {
    mockFind.mockResolvedValue(null);
    mockSearch.mockResolvedValue({
      items: [
        { id: "email-a" } as ProductEmailDetail["email"],
        { id: "email-b" } as ProductEmailDetail["email"],
      ],
      total: 2,
      skip: 0,
      limit: 10,
    });

    const provider = new FakeCurrentMailContextProvider({ subject: "Draft BL check" });
    const adapter = new IdentityAdapter(provider);
    const result = await adapter.resolve();

    expect(result.strategy).toBe("not_resolved");
    expect(result.confidence).toBe("none");
    expect(result.detail).toBeNull();
  });

  it("returns not_resolved when context is unavailable", async () => {
    const provider = new FakeCurrentMailContextProvider(null);
    const adapter = new IdentityAdapter(provider);
    const result = await adapter.resolve();
    expect(result.strategy).toBe("not_resolved");
    expect(result.detail).toBeNull();
  });

  it("documents the Graph identity limitation when not resolved", async () => {
    mockFind.mockResolvedValue(null);
    mockSearch.mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 });
    const provider = new FakeCurrentMailContextProvider({ subject: "Some email" });
    const adapter = new IdentityAdapter(provider);
    const result = await adapter.resolve();
    expect(result.limitationNote).not.toBeNull();
    expect(result.limitationNote).toContain("not been found");
  });
});
