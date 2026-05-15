import { Link2, RotateCcw, Sparkles } from "lucide-react";
import { FormEvent } from "react";

import { Button } from "../../shared/components/Button";

type UrlInputPanelProps = {
  value: string;
  disabled?: boolean;
  exampleUrl: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function UrlInputPanel({
  disabled = false,
  exampleUrl,
  onChange,
  onSubmit,
  value
}: UrlInputPanelProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="url-panel" onSubmit={handleSubmit}>
      <label className="field-label" htmlFor="post-url">
        Bluesky post URL
      </label>
      <div className="url-command">
        <Link2 aria-hidden size={18} />
        <input
          disabled={disabled}
          id="post-url"
          onChange={(event) => onChange(event.target.value)}
          placeholder="https://bsky.app/profile/.../post/..."
          value={value}
        />
        <Button disabled={disabled} icon={<Sparkles size={17} />} type="submit">
          Explain
        </Button>
      </div>
      <Button
        className="example-button"
        disabled={disabled}
        icon={<RotateCcw size={16} />}
        onClick={() => onChange(exampleUrl)}
        variant="ghost"
      >
        Try example
      </Button>
    </form>
  );
}
