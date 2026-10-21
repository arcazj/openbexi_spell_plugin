"""Run independent native suites concurrently, retaining their original gates."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import uuid

from run_language_regressions import ROOT, SUITES, sha, validate_report, report_from_stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    parser.add_argument('--reuse', type=Path, help='Verify each retained passing suite before reuse')
    args = parser.parse_args()
    image = subprocess.check_output(['docker','image','inspect',args.image,'--format','{{.Id}}'],text=True).strip()
    output = args.output.resolve() / uuid.uuid4().hex
    output.mkdir(parents=True)
    result = dict(passed=False, complete_sequence=True, state='running', image=image,
                  source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  runner_sha256=sha(Path(__file__)), workers=args.workers, suites=[])
    retained = {}
    if args.reuse:
        old = json.loads(args.reuse.read_bytes())
        assert old['image'] == image
        for stage in old['suites']:
            if stage['passed'] and stage['exit_code'] == 0:
                retained[stage['suite']] = stage
    def run(suite):
        name, script, options, minimum = suite
        if name in retained:
            stage = retained[name]
            assert sha(Path(stage['log']['path'])) == stage['log']['sha256']
            assert validate_report(Path(stage['raw']['path']),image,minimum) == stage['raw']
            return stage
        command = [sys.executable,'-X','utf8',str(ROOT/'conformance'/script),*options,'--image',image]
        print('Running '+name,flush=True)
        process = subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        log = output / (name+'.log')
        log.write_text(process.stdout+'\n'+process.stderr,encoding='utf-8',newline='\n')
        stage = dict(suite=name,command=command,exit_code=process.returncode,
                     log=dict(path=str(log),sha256=sha(log)),passed=False)
        try:
            stage['raw'] = validate_report(report_from_stdout(process.stdout),image,minimum)
            assert process.returncode == 0
            stage['passed'] = True
        except Exception as error:
            stage['error'] = str(error)
        print(name+': '+('PASS' if stage['passed'] else 'FAIL '+stage.get('error','')),flush=True)
        return stage
    completed = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run,suite) for suite in SUITES]
        for future in as_completed(futures):
            stage = future.result()
            completed[stage['suite']] = stage
            result['suites'] = [completed[s[0]] for s in SUITES if s[0] in completed]
            (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    result['passed'] = len(completed) == len(SUITES) and all(s['passed'] for s in result['suites'])
    result['state'] = 'complete' if result['passed'] else 'failed'
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=result['passed'],suites=len(completed),evidence=str(output))),flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
