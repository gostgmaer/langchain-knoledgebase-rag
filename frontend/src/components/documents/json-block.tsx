/** Pretty-printed JSON, scrollable. */
export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-72 overflow-auto rounded-md bg-neutral-100 p-3 text-xs dark:bg-neutral-900">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}
