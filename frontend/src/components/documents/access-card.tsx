"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useUpdateDocument } from "@/hooks/use-api";
import type { DocumentRecord } from "@/lib/api/types";

/** Who may retrieve this document, and how it is classified (used by search filters). */
export function AccessCard({ doc }: { doc: DocumentRecord }) {
  const update = useUpdateDocument(doc.id);
  const [visibility, setVisibility] = useState(doc.visibility);
  const [documentType, setDocumentType] = useState(doc.document_type ?? "");
  const [category, setCategory] = useState(doc.category ?? "");
  const [tags, setTags] = useState((doc.tags ?? []).join(", "));
  const [roles, setRoles] = useState((doc.allowed_roles ?? []).join(", "));
  const [users, setUsers] = useState((doc.allowed_users ?? []).join(", "));
  const list = (value: string) => value.split(",").map((t) => t.trim()).filter(Boolean);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await update.mutateAsync({
        visibility,
        document_type: documentType.trim() || null,
        category: category.trim() || null,
        tags: list(tags),
        allowed_roles: list(roles),
        allowed_users: list(users),
      });
      toast.success("Document access and classification saved.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Access &amp; classification</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="grid gap-3 text-sm">
          <label className="grid gap-1">
            <span className="text-neutral-500">Who can retrieve it</span>
            <Select value={visibility} onChange={(e) => setVisibility(e.target.value as "tenant" | "restricted")}>
              <option value="tenant">All members of the workspace</option>
              <option value="restricted">Restricted (administrators, plus the grants below)</option>
            </Select>
          </label>
          {visibility === "restricted" && (
            <>
              <label className="grid gap-1">
                <span className="text-neutral-500">Also allow these roles (comma-separated)</span>
                <Input value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="member, finance" />
              </label>
              <label className="grid gap-1">
                <span className="text-neutral-500">Also allow these user ids (comma-separated)</span>
                <Input value={users} onChange={(e) => setUsers(e.target.value)} placeholder="user uuid, user uuid" />
              </label>
            </>
          )}
          <label className="grid gap-1">
            <span className="text-neutral-500">Type</span>
            <Input value={documentType} onChange={(e) => setDocumentType(e.target.value)} placeholder="policy" />
          </label>
          <label className="grid gap-1">
            <span className="text-neutral-500">Category</span>
            <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="hr" />
          </label>
          <label className="grid gap-1">
            <span className="text-neutral-500">Tags (comma-separated)</span>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="2026, europe" />
          </label>
          <p className="text-xs text-neutral-400">
            Access changes apply to the next question; nothing is re-indexed. Each change is recorded in the audit trail.
          </p>
          <Button type="submit" loading={update.isPending} className="justify-self-start">
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
