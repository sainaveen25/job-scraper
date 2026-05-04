import { createWriteStream } from "node:fs";
import { mkdir, readdir, stat } from "node:fs/promises";
import { join, relative } from "node:path";

await import("./build.mjs");

const outDir = "release";
await mkdir(outDir, { recursive: true });
const zipPath = join(outDir, "applymate-ai-extension-0.1.0.zip");
const output = createWriteStream(zipPath);
const CRC_TABLE = createCrcTable();

const files = await walk("dist");
await writeZip(files, output);
console.log(`Created ${zipPath}`);

async function walk(dir) {
  const entries = await readdir(dir);
  const files = [];
  for (const entry of entries) {
    const full = join(dir, entry);
    const info = await stat(full);
    if (info.isDirectory()) {
      files.push(...await walk(full));
    } else {
      files.push(full);
    }
  }
  return files;
}

async function writeZip(files, stream) {
  const central = [];
  let offset = 0;
  for (const file of files) {
    const data = await (await import("node:fs/promises")).readFile(file);
    const name = relative("dist", file).replace(/\\/g, "/");
    const crc = crc32(data);
    const local = localHeader(name, data.length, crc);
    stream.write(local);
    stream.write(data);
    central.push({ name, size: data.length, offset, crc });
    offset += local.length + data.length;
  }
  const centralStart = offset;
  for (const item of central) {
    const record = centralHeader(item.name, item.size, item.offset, item.crc);
    stream.write(record);
    offset += record.length;
  }
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(central.length, 8);
  end.writeUInt16LE(central.length, 10);
  end.writeUInt32LE(offset - centralStart, 12);
  end.writeUInt32LE(centralStart, 16);
  stream.end(end);
  await new Promise((resolve) => stream.on("finish", resolve));
}

function localHeader(name, size, crc) {
  const filename = Buffer.from(name);
  const fixed = Buffer.alloc(30);
  fixed.writeUInt32LE(0x04034b50, 0);
  fixed.writeUInt16LE(20, 4);
  fixed.writeUInt32LE(crc, 14);
  fixed.writeUInt32LE(size, 18);
  fixed.writeUInt32LE(size, 22);
  fixed.writeUInt16LE(filename.length, 26);
  return Buffer.concat([fixed, filename]);
}

function centralHeader(name, size, offset, crc) {
  const filename = Buffer.from(name);
  const fixed = Buffer.alloc(46);
  fixed.writeUInt32LE(0x02014b50, 0);
  fixed.writeUInt16LE(20, 4);
  fixed.writeUInt16LE(20, 6);
  fixed.writeUInt32LE(crc, 16);
  fixed.writeUInt32LE(size, 20);
  fixed.writeUInt32LE(size, 24);
  fixed.writeUInt16LE(filename.length, 28);
  fixed.writeUInt32LE(offset, 42);
  return Buffer.concat([fixed, filename]);
}

function crc32(buffer) {
  let crc = -1;
  for (const byte of buffer) {
    crc = (crc >>> 8) ^ CRC_TABLE[(crc ^ byte) & 0xff];
  }
  return (crc ^ -1) >>> 0;
}

function createCrcTable() {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
}
