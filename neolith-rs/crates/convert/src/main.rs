use neolith_convert::{export_lakes, export_map, export_rivers, import_lakes, export_settlements, import_map, import_rivers, import_settlements, stats};
use neolith_core::{io, World};
use std::io::BufWriter;
use std::process::ExitCode;

const USAGE: &str = "\
neolith-convert: GeoJSON ⇄ world.bin

USAGE:
  neolith-convert <combined_map.geojson> [settlements.geojson] [--rivers <rivers.geojson>] [--lakes <lakes.geojson>] -o <world.bin>
  neolith-convert --to-geojson <world.bin> -o <combined_map.geojson> [--settlements-out <file>] [--rivers-out <file>] [--lakes-out <file>]
  neolith-convert --stats <world.bin | combined_map.geojson> [settlements.geojson]
";

fn read_text(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))
}

/// Loads a world from either a `world.bin` or the GeoJSON inputs.
fn load(inputs: &[String], rivers: Option<&str>, lakes: Option<&str>) -> Result<World, String> {
    let first = inputs.first().ok_or("no input file given")?;
    let bytes = std::fs::read(first).map_err(|e| format!("cannot read {first}: {e}"))?;
    if bytes.starts_with(&io::MAGIC) {
        return io::decode(&bytes).map_err(|e| format!("{first}: {e}"));
    }
    let text = String::from_utf8(bytes).map_err(|_| format!("{first}: neither a world.bin nor UTF-8 GeoJSON"))?;
    let import = import_map(&text)?;
    for w in &import.warnings {
        eprintln!("warning: {w}");
    }
    let mut world = import.world;
    if let Some(path) = inputs.get(1) {
        let (settlements, warnings) = import_settlements(&read_text(path)?)?;
        for w in &warnings {
            eprintln!("warning: {w}");
        }
        world.settlements = settlements;
    } else {
        eprintln!("note: no settlements file given; the world has no settlements");
    }
    match rivers {
        Some(path) => world.rivers = import_rivers(&read_text(path)?)?,
        None => eprintln!("note: no --rivers file given; the world has no river lines"),
    }
    match lakes {
        Some(path) => world.lakes = import_lakes(&read_text(path)?)?,
        None => eprintln!("note: no --lakes file given; the world has no lake shorelines"),
    }
    Ok(world)
}

fn run() -> Result<(), String> {
    let mut inputs = Vec::new();
    let (mut out, mut settlements_out) = (None, None);
    let (mut rivers, mut rivers_out) = (None, None);
    let (mut lakes, mut lakes_out) = (None, None);
    let (mut to_geojson, mut want_stats) = (false, false);
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "-o" | "--output" => out = Some(args.next().ok_or("-o needs a path")?),
            "--settlements-out" => settlements_out = Some(args.next().ok_or("--settlements-out needs a path")?),
            "--rivers" => rivers = Some(args.next().ok_or("--rivers needs a path")?),
            "--lakes" => lakes = Some(args.next().ok_or("--lakes needs a path")?),
            "--lakes-out" => lakes_out = Some(args.next().ok_or("--lakes-out needs a path")?),
            "--rivers-out" => rivers_out = Some(args.next().ok_or("--rivers-out needs a path")?),
            "--to-geojson" => to_geojson = true,
            "--stats" => want_stats = true,
            "-h" | "--help" => {
                print!("{USAGE}");
                return Ok(());
            }
            s if s.starts_with('-') => return Err(format!("unknown option {s}\n\n{USAGE}")),
            _ => inputs.push(a),
        }
    }
    if inputs.is_empty() {
        return Err(USAGE.to_string());
    }
    let world = load(&inputs, rivers.as_deref(), lakes.as_deref())?;

    if want_stats {
        print!("{}", stats(&world));
    }
    if to_geojson {
        let path = out.ok_or("--to-geojson needs -o <combined_map.geojson>")?;
        let file = std::fs::File::create(&path).map_err(|e| format!("cannot create {path}: {e}"))?;
        export_map(&world, BufWriter::new(file)).map_err(|e| format!("cannot write {path}: {e}"))?;
        eprintln!("wrote {path} ({} hexes)", world.grid.len());
        if let Some(path) = settlements_out {
            let text = serde_json::to_string_pretty(&export_settlements(&world)).unwrap();
            std::fs::write(&path, text).map_err(|e| format!("cannot write {path}: {e}"))?;
            eprintln!("wrote {path} ({} settlements)", world.settlements.len());
        }
        if let Some(path) = rivers_out {
            let text = serde_json::to_string(&export_rivers(&world)).unwrap();
            std::fs::write(&path, text).map_err(|e| format!("cannot write {path}: {e}"))?;
            eprintln!("wrote {path} ({} river stretches)", world.rivers.len());
        }
        if let Some(path) = lakes_out {
            let text = serde_json::to_string(&export_lakes(&world)).unwrap();
            std::fs::write(&path, text).map_err(|e| format!("cannot write {path}: {e}"))?;
            eprintln!("wrote {path} ({} lakes)", world.lakes.len());
        }
    } else if let Some(path) = out {
        let bytes = io::encode(&world);
        std::fs::write(&path, &bytes).map_err(|e| format!("cannot write {path}: {e}"))?;
        eprintln!(
            "wrote {path}: {} hexes, {} keyframes, {} settlements, {} river stretches, {} lakes, {:.1} KB",
            world.grid.len(),
            world.keyframe_years().len(),
            world.settlements.len(),
            world.rivers.len(),
            world.lakes.len(),
            bytes.len() as f64 / 1024.0
        );
    } else if !want_stats {
        return Err(format!("nothing to do: give -o <file> or --stats\n\n{USAGE}"));
    }
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}
