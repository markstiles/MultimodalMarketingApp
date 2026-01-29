import { NextRequest, NextResponse } from 'next/server';
import AdmZip from 'adm-zip';
import { XMLParser } from 'fast-xml-parser';

// Helper to extract text from a run
const getRunText = (r: any) => {
    let text = '';
    if (r['w:t']) {
        const t = r['w:t'];
        if (typeof t === 'string') text += t;
        else if (t['#text']) text += t['#text'];
    }
    return text;
};

// Helper to process a paragraph
const processParagraph = (p: any): string => {
    let pHtml = '<p>';
    let isHeading = false;
    let headingLevel = 1;

    // Check for styles (Headings)
    if (p['w:pPr'] && p['w:pPr']['w:pStyle'] && p['w:pPr']['w:pStyle']['@_w:val']) {
        const styleId = p['w:pPr']['w:pStyle']['@_w:val'];
        const headingMatch = styleId.match(/Heading(\d+)/i);
        if (headingMatch) {
            isHeading = true;
            headingLevel = parseInt(headingMatch[1]);
        }
    }

    if (isHeading) {
        pHtml = `<h${headingLevel}>`;
    }

    // Process runs
    const runs = p['w:r'];
    if (runs) {
        if (Array.isArray(runs)) {
            runs.forEach(r => {
                pHtml += getRunText(r);
            });
        } else {
            pHtml += getRunText(runs);
        }
    }

    if (isHeading) {
        pHtml += `</h${headingLevel}>`;
    } else {
        pHtml += '</p>';
    }

    // Simplistic check for empty paragraphs
    if (pHtml === '<p></p>') return '';
    
    return pHtml;
};

// Recursive processing of body elements
const processBodyElements = (elements: any): string => {
    let html = '';
    
    const processElement = (key: string, value: any) => {
        if (key === 'w:p') {
            if (Array.isArray(value)) {
                value.forEach(p => html += processParagraph(p));
            } else {
                html += processParagraph(value);
            }
        } else if (key === 'w:tbl') { // Simple table handling
            html += '<table>';
            const rows = value['w:tr'];
            if (Array.isArray(rows)) {
                rows.forEach((row: any) => {
                    html += '<tr>';
                    const cells = row['w:tc'];
                    if (Array.isArray(cells)) {
                        cells.forEach((cell: any) => {
                            html += '<td>';
                            if (cell['w:p']) { // Cell content is usually paragraphs
                                    if(Array.isArray(cell['w:p'])) {
                                    cell['w:p'].forEach((p: any) => html += processParagraph(p));
                                    } else {
                                    html += processParagraph(cell['w:p']);
                                    }
                            }
                            html += '</td>';
                        });
                    } else if (cells) {
                            html += '<td>';
                            if(cells['w:p']) html += processParagraph(cells['w:p']);
                            html += '</td>';
                    }
                    html += '</tr>';
                });
            }
            html += '</table>';
        } else if (key === 'w:sdt') { // Content controls
                if (value['w:sdtContent']) {
                    // Recursively process content of sdt
                    Object.keys(value['w:sdtContent']).forEach(k => {
                        processElement(k, value['w:sdtContent'][k]);
                    });
                }
        }
    };

    if (elements) {
            Object.keys(elements).forEach(key => {
                processElement(key, elements[key]);
            });
    }
    
    return html;
};

async function parseDocx(buffer: Buffer): Promise<{ html: string, text: string }> {
    // Unzip the file
    const zip = new AdmZip(buffer);
    const zipEntries = zip.getEntries();
    
    // Find word/document.xml
    const documentEntry = zipEntries.find(entry => entry.entryName === 'word/document.xml');
    
    let documentXml = '';
    if (documentEntry) {
        documentXml = documentEntry.getData().toString('utf8');
    } else {
         throw new Error('Could not find word/document.xml in the provided file.');
    }

    // Parse XML
    const parser = new XMLParser({
        ignoreAttributes: false,
        attributeNamePrefix: "@_"
    });
    const jsonObj = parser.parse(documentXml);
    
    let parsedHtml = '';
    if (jsonObj['w:document'] && jsonObj['w:document']['w:body']) {
        const body = jsonObj['w:document']['w:body'];
        parsedHtml = processBodyElements(body);
    }
    
    // Also extract raw text for the AI prompt
    const parsedText = parsedHtml.replace(/<[^>]+>/g, '\n').replace(/\n+/g, '\n').trim();

    return { html: parsedHtml, text: parsedText };
}


export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    const fileName = file.name.toLowerCase();
    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    
    let html = '';
    let text = '';

    if (fileName.endsWith('.docx')) {
        const result = await parseDocx(buffer);
        html = result.html;
        text = result.text;
    } else if (fileName.endsWith('.pdf')) {
        // @ts-ignore
        // Direct import to bypass index.js debug logic that attempts to read a test file
        const pdf = require('pdf-parse/lib/pdf-parse.js');
        const data = await pdf(buffer);
        text = data.text;
        // Basic HTML formatting for PDF text
        text = data.text;
        // Basic HTML formatting for PDF text
        // Split by newlines and wrap in p tags, filtering empty lines
        html = text.split('\n')
            .map((line: string) => line.trim())
            .filter((line: string) => line.length > 0)
            .map((line: string) => `<p>${line}</p>`)
            .join('');
    } else if (fileName.endsWith('.txt') || fileName.endsWith('.md')) {
        text = buffer.toString('utf-8');
        if (fileName.endsWith('.md')) {
             // For markdown, we want to preserve format but maybe hint it's markdown
             html = `<div style="white-space: pre-wrap;">${text}</div>`;
        } else {
             html = `<pre style="white-space: pre-wrap;">${text}</pre>`;
        }
    } else {
         return NextResponse.json({ error: 'Invalid file type. Supported: .docx, .pdf, .txt, .md' }, { status: 400 });
    }

    return NextResponse.json({ 
        success: true, 
        text: text,
        html: html
    });

  } catch (error) {
    console.error('Error processing document:', error);
    return NextResponse.json({ error: 'Failed to process document' }, { status: 500 });
  }
}
