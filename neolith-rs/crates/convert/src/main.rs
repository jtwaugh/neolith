use neolith_convert::{
    attach_dates, export_lakes, export_map, export_rivers, export_settlements, import_cultures, import_evidence, import_lakes, import_samples, import_map, import_rivers,
    import_settlement_records, stats, append_inferred,
};
use neolith_core::{io, World};
use std::io::BufWriter;
use std::process::ExitCode;

const USAGE: &str = "\
neolith-convert: GeoJSON ⇄ world.bin

USAGE:
  neolith-convert <combined_map.geojson> [settlements.geojson] [--rivers <rivers.geojson>] [--lakes <lakes.geojson>]
                   [--dates <dates.csv[.gz]>] [--cultures <cultures.json>] [--evidence <evidence_layers.json>]
                   [--inferred <inferred.geojson>] [--heightmap <etopo.asc>] [--samples <ancestry_samples.json>] -o <world.bin>
  neolith-convert <world.bin> --heightmap <etopo.asc> -o <world.bin>
  neolith-convert --attach-evidence <evidence_layers.json> <world.bin> -o <world.bin>
  neolith-convert --attach-samples <ancestry_samples.json> <world.bin> -o <world.bin>
                   (sets the world's ancestry samples; no GeoJSON needed)
  neolith-convert <world.bin> --residuals <residuals.csv[.gz]> -o <world.bin>
                   (sets the world's missing-sites table; also accepted when building from GeoJSON)
                   (replaces the world's evidence layers; no GeoJSON needed)
  neolith-convert --to-geojson <world.bin> -o <combined_map.geojson> [--settlements-out <file>] [--rivers-out <file>] [--lakes-out <file>]
  neolith-convert --stats <world.bin | combined_map.geojson> [settlements.geojson]
  neolith-convert <world.bin> --expected <expected.csv> [--years -10000,-9000,...]
";

fn read_text(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))
}

/// Loads a world from either a `world.bin` or the GeoJSON inputs.
/// Reads a file, un-gzipping it if its name ends in `.gz`.
fn read_maybe_gz(path: &str) -> Result<String, String> {
    if !path.ends_with(".gz") {
        return read_text(path);
    }
    let file = std::fs::File::open(path).map_err(|e| format!("cannot read {path}: {e}"))?;
    let mut text = String::new();
    std::io::Read::read_to_string(&mut flate2::read::GzDecoder::new(file), &mut text)
        .map_err(|e| format!("cannot read {path}: {e}"))?;
    Ok(text)
}

/// Optional inputs besides the map and settlements.
#[derive(Default)]
struct Extras {
    rivers: Option<String>,
    lakes: Option<String>,
    dates: Option<String>,
    cultures: Option<String>,
    /// isostyle's `evidence_layers.json`.
    evidence: Option<String>,
    /// isostyle's `ancestry_samples.json`.
    samples: Option<String>,
    /// The pipeline's `residuals.csv[.gz]`.
    residuals: Option<String>,
    /// The pipeline's `inferred.geojson`: inferred settlements, appended
    /// after the recorded ones.
    inferred: Option<String>,
    /// An ESRI ASCII elevation grid (`build/etopo.asc`): the heightmap the
    /// board lights relief from.
    heightmap: Option<String>,
}

fn load(inputs: &[String], extras: &Extras) -> Result<World, String> {
    let (rivers, lakes) = (extras.rivers.as_deref(), extras.lakes.as_deref());
    let first = inputs.first().ok_or("no input file given")?;
    let bytes = std::fs::read(first).map_err(|e| format!("cannot read {first}: {e}"))?;
    if bytes.starts_with(&io::MAGIC) {
        let mut world = io::decode(&bytes).map_err(|e| format!("{first}: {e}"))?;
        if extras.heightmap.is_some() {
            attach_heightmap(&mut world, extras)?;
        }
        return Ok(world);
    }
    let text = String::from_utf8(bytes).map_err(|_| format!("{first}: neither a world.bin nor UTF-8 GeoJSON"))?;
    let import = import_map(&text)?;
    for w in &import.warnings {
        eprintln!("warning: {w}");
    }
    let mut world = import.world;
    if let Some(path) = inputs.get(1) {
        let (settlements, mut info, warnings) = import_settlement_records(&read_text(path)?)?;
        for w in &warnings {
            eprintln!("warning: {w}");
        }
        match &extras.dates {
            Some(dates) => {
                let (n, orphans) = attach_dates(&settlements, &mut info, &read_maybe_gz(dates)?)?;
                eprintln!("{n} radiocarbon dates attached");
                if orphans > 0 {
                    eprintln!("warning: {orphans} dates name a settlement not in {path}");
                }
            }
            None => eprintln!("note: no --dates file given; site records have no radiocarbon dates"),
        }
        world.settlements = settlements;
        world.site_info = info;
    } else {
        eprintln!("note: no settlements file given; the world has no settlements");
    }
    if let Some(path) = &extras.inferred {
        let n = append_inferred(&mut world, &read_text(path)?)?;
        eprintln!("{n} inferred settlements added from {path}");
    }
    match rivers {
        Some(path) => world.rivers = import_rivers(&read_text(path)?)?,
        None => eprintln!("note: no --rivers file given; the world has no river lines"),
    }
    match lakes {
        Some(path) => world.lakes = import_lakes(&read_text(path)?)?,
        None => eprintln!("note: no --lakes file given; the world has no lake shorelines"),
    }
    if let Some(path) = &extras.cultures {
        world.cultures = import_cultures(&read_text(path)?)?;
    }
    attach_heightmap(&mut world, extras)?;
    Ok(world)
}

fn attach_heightmap(world: &mut World, extras: &Extras) -> Result<(), String> {
    match &extras.heightmap {
        Some(path) => {
            let h = neolith_convert::import_heightmap(&read_text(path)?, &world.grid)?;
            eprintln!("heightmap: {} x {} cells of {}° from {path}", h.cols, h.rows, h.cell);
            world.heightmap = Some(h);
        }
        None => eprintln!("note: no --heightmap file given; the board lights relief from the hex heights"),
    }
    Ok(())
}

fn run() -> Result<(), String> {
    let mut inputs = Vec::new();
    let (mut out, mut settlements_out) = (None, None);
    let mut extras = Extras::default();
    let (mut rivers_out, mut lakes_out) = (None, None);
    let (mut to_geojson, mut want_stats) = (false, false);
    let mut expected_out = None;
    let mut attach = false;
    let mut years: Vec<neolith_core::Year> = (-10..=-3).map(|k| neolith_core::Year(k * 1000)).collect();
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "-o" | "--output" => out = Some(args.next().ok_or("-o needs a path")?),
            "--settlements-out" => settlements_out = Some(args.next().ok_or("--settlements-out needs a path")?),
            "--rivers" => extras.rivers = Some(args.next().ok_or("--rivers needs a path")?),
            "--lakes" => extras.lakes = Some(args.next().ok_or("--lakes needs a path")?),
            "--dates" => extras.dates = Some(args.next().ok_or("--dates needs a path")?),
            "--cultures" => extras.cultures = Some(args.next().ok_or("--cultures needs a path")?),
            "--evidence" => extras.evidence = Some(args.next().ok_or("--evidence needs a path")?),
            "--attach-evidence" => {
                extras.evidence = Some(args.next().ok_or("--attach-evidence needs a path")?);
                attach = true;
            }
            "--samples" => extras.samples = Some(args.next().ok_or("--samples needs a path")?),
            "--attach-samples" => {
                extras.samples = Some(args.next().ok_or("--attach-samples needs a path")?);
                attach = true;
            }
            "--heightmap" => extras.heightmap = Some(args.next().ok_or("--heightmap needs a path")?),
            "--inferred" => extras.inferred = Some(args.next().ok_or("--inferred needs a path")?),
            "--residuals" => extras.residuals = Some(args.next().ok_or("--residuals needs a path")?),
            "--lakes-out" => lakes_out = Some(args.next().ok_or("--lakes-out needs a path")?),
            "--rivers-out" => rivers_out = Some(args.next().ok_or("--rivers-out needs a path")?),
            "--to-geojson" => to_geojson = true,
            "--stats" => want_stats = true,
            "--expected" => expected_out = Some(args.next().ok_or("--expected needs a path")?),
            "--years" => {
                let list = args.next().ok_or("--years needs a comma-separated list")?;
                years = list
                    .split(',')
                    .map(|y| y.trim().parse::<i32>().map(neolith_core::Year).map_err(|_| format!("--years: {y:?} is not a year")))
                    .collect::<Result<_, _>>()?;
            }
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
    if attach && !inputs.first().is_some_and(|p| std::fs::read(p).is_ok_and(|b| b.starts_with(&io::MAGIC))) {
        return Err("--attach-evidence and --attach-samples need a world.bin input (use --evidence and --samples when building from GeoJSON)".into());
    }
    let mut world = load(&inputs, &extras)?;
    if let Some(path) = &extras.evidence {
        world.evidence = import_evidence(&read_text(path)?, world.grid.len()).map_err(|e| format!("{path}: {e}"))?;
        world.validate().map_err(|e| format!("{path}: {e}"))?;
        eprintln!("{} evidence layers from {path}", world.evidence.len());
    }
    if let Some(path) = &extras.samples {
        let table = import_samples(&read_text(path)?).map_err(|e| format!("{path}: {e}"))?;
        eprintln!("{} ancestry samples from {path}", table.samples.len());
        world.ancestry = Some(table);
        world.validate().map_err(|e| format!("{path}: {e}"))?;
    }
    if let Some(path) = &extras.residuals {
        let table = neolith_convert::import_residuals(&read_maybe_gz(path)?, world.grid.len()).map_err(|e| format!("{path}: {e}"))?;
        eprintln!("residuals for {} epochs from {path}", table.slices.len());
        world.residuals = Some(table);
        world.validate().map_err(|e| format!("{path}: {e}"))?;
    }

    if want_stats {
        print!("{}", stats(&world));
    }
    let wrote_expected = expected_out.is_some();
    if let Some(path) = expected_out {
        let text = neolith_convert::expected_csv(&world, &years);
        std::fs::write(&path, &text).map_err(|e| format!("cannot write {path}: {e}"))?;
        eprintln!("wrote {path} ({} rows, {} years)", text.lines().count() - 1, years.len());
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
            "wrote {path}: {} hexes, {} keyframes, {} settlements, {} river stretches, {} lakes, {} evidence layers, {:.1} KB",
            world.grid.len(),
            world.keyframe_years().len(),
            world.settlements.len(),
            world.rivers.len(),
            world.lakes.len(),
            world.evidence.len(),
            bytes.len() as f64 / 1024.0
        );
    } else if !want_stats && !wrote_expected {
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
