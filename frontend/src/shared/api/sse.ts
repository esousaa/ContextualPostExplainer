export type SseMessage = {
  event: string;
  data: string;
};

export function extractSseMessages(buffer: string): {
  messages: SseMessage[];
  remaining: string;
} {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const remaining = parts.pop() ?? "";
  const messages = parts.map(parseSseMessage).filter((message): message is SseMessage => message !== null);

  return { messages, remaining };
}

export async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  onMessage: (message: SseMessage) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const parsed = extractSseMessages(buffer);
    buffer = parsed.remaining;
    parsed.messages.forEach(onMessage);

    if (done) {
      break;
    }
  }

  const lastMessage = parseSseMessage(buffer.trim());
  if (lastMessage) {
    onMessage(lastMessage);
  }
}

function parseSseMessage(raw: string): SseMessage | null {
  if (!raw.trim()) {
    return null;
  }

  let event = "message";
  const dataLines: string[] = [];

  for (const line of raw.split(/\n/)) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  return {
    event,
    data: dataLines.join("\n"),
  };
}
