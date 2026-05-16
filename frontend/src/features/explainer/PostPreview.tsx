import { CalendarDays, ExternalLink, Image as ImageIcon, Link as LinkIcon } from "lucide-react";

import { Badge } from "../../shared/components/Badge";
import { formatDate } from "../../shared/utils/date";
import { safeExternalUrl } from "../../shared/utils/url";
import type { PostData } from "./types";

type PostPreviewProps = {
  post: PostData | null;
};

export function PostPreview({ post }: PostPreviewProps) {
  if (!post) {
    return (
      <section className="post-preview empty-preview" aria-label="Post preview">
        <div className="avatar">BS</div>
        <div>
          <h2>Ready</h2>
          <p>No post loaded.</p>
        </div>
      </section>
    );
  }

  const displayName = post.author.display_name || post.author.handle;
  const originalPostUrl = safeExternalUrl(post.url);

  return (
    <section className="post-preview" aria-label="Post preview">
      <div className="avatar">{initials(displayName)}</div>
      <div className="post-body">
        <div className="post-meta">
          <strong>{displayName}</strong>
          <span>@{post.author.handle}</span>
          {originalPostUrl && (
            <a href={originalPostUrl} rel="noreferrer" target="_blank" title="Open original post">
              <ExternalLink size={15} />
            </a>
          )}
        </div>
        <p>{post.text}</p>
        <div className="post-facts">
          <Badge tone="neutral">
            <CalendarDays size={13} />
            {formatDate(post.created_at)}
          </Badge>
          <Badge tone="teal">{post.platform}</Badge>
          <Badge tone={post.images.length > 0 ? "blue" : "neutral"}>
            <ImageIcon size={13} />
            {post.images.length} images
          </Badge>
          <Badge tone={post.links.length > 0 ? "blue" : "neutral"}>
            <LinkIcon size={13} />
            {post.links.length} links
          </Badge>
        </div>
        {post.images.length > 0 && (
          <div className="image-list">
            {post.images.map((image, index) => {
              const imageUrl = safeExternalUrl(image.url);
              return (
                <figure key={`${image.url ?? "image"}-${index}`}>
                  {imageUrl && <img alt={image.alt_text ?? image.description ?? ""} src={imageUrl} />}
                  <figcaption>
                    {image.image_type && <span className="image-type">{image.image_type}</span>}
                    {image.alt_text && <ImageTextBlock label="Alt text" text={image.alt_text} />}
                    {image.ocr_text && <ImageTextBlock label="Extracted text" text={image.ocr_text} />}
                    {image.description && (
                      <ImageTextBlock label="Visual description" text={image.description} />
                    )}
                    {!image.alt_text && !image.ocr_text && !image.description && "Image without alt text."}
                  </figcaption>
                </figure>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

function ImageTextBlock({ label, text }: { label: string; text: string }) {
  return (
    <span className="image-text-block">
      <strong>{label}</strong>
      <span>{text}</span>
    </span>
  );
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
