export interface ErrorSegment {
  type: 'text' | 'error';
  value: string;
  filePath?: string;
}

const ERROR_LINE_RE =
  /(Traceback \(most recent call last\):|NameError:|ModuleNotFoundError:|SyntaxError:|IndentationError:|TypeError:|AttributeError:|FileNotFoundError:|Проверка кода не прошла:|Проверка не прошла:|Код выхода:|✗ Код выхода)/i;

const FILE_IN_MESSAGE_RE =
  /(?:Проверка кода не прошла|Проверка не прошла|в файле|file)[:\s]+([^\s\n:]+\.py)/i;

const FILE_QUOTED_RE = /File\s+"([^"]+\.py)"/i;

const PY_FILE_RE = /\b([a-zA-Z0-9_./\\-]+\.py)\b/;

export function extractErrorFilePath(text: string): string | undefined {
  const normalized = text.replace(/\\/g, '/');
  const fromMessage = normalized.match(FILE_IN_MESSAGE_RE);
  if (fromMessage?.[1]) {
    return fromMessage[1].replace(/\\/g, '/').split('/').pop();
  }
  const quoted = normalized.match(FILE_QUOTED_RE);
  if (quoted?.[1]) {
    const parts = quoted[1].replace(/\\/g, '/').split('/');
    return parts[parts.length - 1];
  }
  const generic = normalized.match(PY_FILE_RE);
  return generic?.[1]?.replace(/\\/g, '/').split('/').pop();
}

export function splitErrorSegments(text: string): ErrorSegment[] {
  if (!text.trim()) {
    return [{ type: 'text', value: text }];
  }

  const lines = text.split('\n');
  const segments: ErrorSegment[] = [];
  let buffer: string[] = [];
  let errorBuffer: string[] = [];
  let inError = false;

  const flushText = () => {
    if (buffer.length) {
      segments.push({ type: 'text', value: buffer.join('\n') });
      buffer = [];
    }
  };

  const flushError = () => {
    if (errorBuffer.length) {
      const value = errorBuffer.join('\n');
      segments.push({
        type: 'error',
        value,
        filePath: extractErrorFilePath(value),
      });
      errorBuffer = [];
    }
  };

  for (const line of lines) {
    const isErrorLine = ERROR_LINE_RE.test(line) || (inError && line.trim().startsWith('^'));
    if (isErrorLine) {
      flushText();
      inError = true;
      errorBuffer.push(line);
      continue;
    }

    if (inError) {
      if (!line.trim()) {
        flushError();
        inError = false;
        buffer.push(line);
      } else if (/^[A-Za-zА-Яа-я]/.test(line) && !line.startsWith('  ')) {
        flushError();
        inError = false;
        buffer.push(line);
      } else {
        errorBuffer.push(line);
      }
      continue;
    }

    buffer.push(line);
  }

  flushText();
  flushError();
  return segments.length ? segments : [{ type: 'text', value: text }];
}
