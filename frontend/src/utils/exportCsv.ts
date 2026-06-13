// \u9632\u6B62 CSV/Excel \u516C\u5F0F\u6CE8\u5165\uFF1A\u4EE5 = + - @ TAB CR \u5F00\u5934\u7684\u5355\u5143\u683C\u5F3A\u5236\u52A0\u524D\u5BFC\u5355\u5F15\u53F7
const FORMULA_PREFIX = /^[=+\-@\t\r]/;
const PLAIN_NUMBER = /^-?\d+(\.\d+)?$/;
function sanitizeCell(raw: unknown): string {
  if (typeof raw === 'number' && Number.isFinite(raw)) return String(raw);
  const text = raw == null ? '' : String(raw);
  if (FORMULA_PREFIX.test(text) && !PLAIN_NUMBER.test(text)) {
    return `'${text}`;
  }
  return text;
}

export function downloadCsv(filename: string, rows: Array<Record<string, string | number>>) {
  const headers = Object.keys(rows[0] ?? {});
  const csv = [
    headers.join(','),
    ...rows.map((row) =>
      headers
        .map((header) => {
          const safe = sanitizeCell(row[header]);
          return `"${safe.replace(/"/g, '""')}"`;
        })
        .join(',')
    )
  ].join('\n');

  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadExcel(filename: string, rows: Array<Record<string, string | number>>) {
  const headers = Object.keys(rows[0] ?? {});
  const escape = (value: string | number) =>
    sanitizeCell(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

  const html = `
    <html>
      <head><meta charset="UTF-8" /></head>
      <body>
        <table>
          <thead><tr>${headers.map((header) => `<th>${escape(header)}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows
              .map((row) => `<tr>${headers.map((header) => `<td>${escape(row[header] ?? '')}</td>`).join('')}</tr>`)
              .join('')}
          </tbody>
        </table>
      </body>
    </html>
  `;

  const blob = new Blob([html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename.endsWith('.xls') ? filename : `${filename}.xls`;
  link.click();
  URL.revokeObjectURL(url);
}
