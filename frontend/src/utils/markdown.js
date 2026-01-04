export function normalizeMarkdownTables(markdown, options = {}) {
  if (typeof markdown !== 'string') {
    return markdown;
  }

  const unwrapFence = options.unwrapFence === true;
  let text = markdown;

  if (unwrapFence) {
    const rawLines = text.split('\n');
    const firstIndex = rawLines.findIndex((line) => line.trim() !== '');
    const lastIndex = rawLines.length - 1 - [...rawLines].reverse().findIndex((line) => line.trim() !== '');
    const firstLine = rawLines[firstIndex]?.trim() || '';
    const lastLine = rawLines[lastIndex]?.trim() || '';
    if (firstLine.startsWith('```') && lastLine === '```' && lastIndex > firstIndex) {
      text = rawLines.slice(firstIndex + 1, lastIndex).join('\n');
    }
  }

  const lines = text.split('\n');
  const output = [];
  let inTable = false;
  let columnCount = 0;
  let inSingleColumn = false;

  const isSeparator = (line) =>
    /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  const getColumnCount = (line) => {
    const parts = line.split('|').map((part) => part.trim());
    if (parts[0] === '') {
      parts.shift();
    }
    if (parts[parts.length - 1] === '') {
      parts.pop();
    }
    return Math.max(parts.length, 1);
  };
  const stripPipes = (line) => {
    const cells = parseRowCells(line);
    return cells.join(' - ').trim();
  };
  const parseRowCells = (line) => {
    const parts = line.split('|').map((part) => part.trim());
    if (parts[0] === '') {
      parts.shift();
    }
    if (parts[parts.length - 1] === '') {
      parts.pop();
    }
    return parts;
  };
  const buildRow = (cells) => `| ${cells.join(' | ')} |`;
  const padCells = (cells) => {
    const padded = [...cells];
    while (columnCount && padded.length < columnCount) {
      padded.push('');
    }
    return padded;
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const next = lines[i + 1];
    const hasPipe = line.includes('|');

    if (!inTable && hasPipe && isSeparator(next || '')) {
      const detectedColumns = getColumnCount(line);
      if (detectedColumns <= 1) {
        const headerText = stripPipes(line);
        if (headerText) {
          output.push(headerText);
        }
        inSingleColumn = true;
        i += 1;
        continue;
      }
      columnCount = detectedColumns;
      output.push(buildRow(padCells(parseRowCells(line))));
      output.push(next);
      inTable = true;
      i += 1;
      continue;
    }

    if (inSingleColumn) {
      if (!hasPipe) {
        inSingleColumn = false;
        output.push(line);
        continue;
      }

      const text = stripPipes(line);
      if (text) {
        output.push(text);
      }
      continue;
    }

    if (inTable) {
      if (line.trim() === '') {
        continue;
      }

      if (hasPipe) {
        const cells = padCells(parseRowCells(line));
        const hasContent = cells.some((cell) => cell.trim() !== '');
        if (hasContent) {
          output.push(buildRow(cells));
        }
        continue;
      }

      inTable = false;
      columnCount = 0;
      output.push(line);
      continue;
    }

    output.push(line);
  }

  return output.join('\n');
}
