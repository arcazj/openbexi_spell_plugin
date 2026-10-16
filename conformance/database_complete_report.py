"""Qualify the whole database chapter only after all backends and formats pass."""
from aggregate_support import ROOT,PREFIX,DIMENSIONS,read,ref,sha,complete_sequence,merge_review_inputs,link_components

ADDITIONAL = ('EXAMPLE-138','SECTION-4-15-2-097','SECTION-4-15-095',
              'SECTION-4-15-6-105','TYPE-DATABASEDICTIONARY')


def combined_checks(base,formats,values,procedure):
    assert all(report['passed'] is True for report in (base,formats,values,procedure))
    assert len({report['runtime_image'] for report in (base,formats,values,procedure)}) == 1
    checks = dict(base['checks'])
    for identifier in ADDITIONAL:
        for dimension in DIMENSIONS:
            deps = []
            if identifier in ('EXAMPLE-138','SECTION-4-15-2-097'):
                for feature in ('load','readonly'):
                    key=feature+'-'+dimension;row=base['manoeuvre_review']['checks'][key]
                    assert row['passed'] is True and row['dimension']==dimension
                    deps.append(dict(report='manoeuvre',check=key))
            else:
                for feature in ('keys','nested-time'):
                    key='formats:'+feature+'-'+dimension;row=formats['checks'][key]
                    assert row['passed'] is True and row['dimension']==dimension
                    deps.append(dict(report='formats',check=key))
                for kind,report in (('octal-and-values',values),('complete-operations',base)):
                    keys=[key for key,row in report['checks'].items() if row.get('dimension')==dimension]
                    assert keys and all(report['checks'][key]['passed'] is True for key in keys)
                    deps.extend(dict(report=kind,check=key) for key in keys)
                if identifier!='SECTION-4-15-6-105':
                    key='procedure-dictionary:'+dimension;row=procedure['checks'][key]
                    assert row['passed'] is True and row['dimension']==dimension
                    deps.append(dict(report='procedure-dictionary',check=key))
            checks[PREFIX+identifier+':'+dimension]=dict(passed=True,dimension=dimension,
                contracts=[PREFIX+identifier],dependencies=deps,
                oracle='Actual native database values, persistence, read-only enforcement, URI routing, typed key/value grammar and failure recovery are all independently checked.')
    return link_components(checks,{'manoeuvre':base['manoeuvre_review'],'formats':formats,
        'octal-and-values':values,'complete-operations':base,'procedure-dictionary':procedure})


def qualify(sequence_path,native_wheel,driver_wheel):
    from database_aggregate_report import qualify as operations_review
    from database_format_review import review as format_review
    from database_values_composed_report import qualify as values_review
    from proc_dictionary_composed_report import qualify as proc_review
    required=('database-formats','database-values','user-database','proc-metadata','proc-lifecycle')
    sequence,paths,raws,inputs=complete_sequence(sequence_path,required)
    image=sequence['image']
    base=operations_review(sequence_path,native_wheel,driver_wheel)
    formats=format_review({'formats':paths['database-formats']},None,None,None,
        sequence['source_commit'],image,native_wheel=native_wheel,driver_wheel=driver_wheel)
    values=values_review(paths['database-values'],paths['user-database'],image)
    procedure=proc_review(paths['proc-metadata'],paths['proc-lifecycle'],image)
    assert formats['composed_wheels']['passed']
    checks=combined_checks(base,formats,values,procedure)
    contracts=sorted(set(base['qualified_contracts'])|{PREFIX+name for name in ADDITIONAL})
    assert len(contracts)==12 and set(contracts)<={r['id'] for r in read(ROOT/'conformance/inventory.json')['rows']}
    merge_review_inputs(inputs,(base,formats,values,procedure))
    for name in ('conformance/database_complete_report.py','conformance/database_format_review.py',
                 'tests/test_database_complete_mapping.py'):
        inputs[name]=sha(ROOT/name)
    return dict(passed=True,runtime_image=image,inputs=inputs,checks=checks,qualified_contracts=contracts,
        sequence=ref(sequence_path),raw={name:ref(path) for name,path in paths.items()},
        independent_reviews=dict(operations=base,formats=formats,values=values,procedure=procedure),
        manual_decisions={'key_types':'LRM p83 lists lists and dictionaries among database data. They are supported as values; unhashable keys retain Python dictionary rejection, before any in-memory or persisted mutation. Typed numeric and quoted string keys retain their types.'},
        full_v05_accepted=False,scope='Complete database chapter in the configured original flat-file backends, including all original dictionary families and persisted typed/nested TIME values.')


if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    parser=argparse.ArgumentParser()
    for name in ('sequence','native-wheel','driver-wheel','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=qualify(args.sequence,args.native_wheel,args.driver_wheel)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,contracts=len(result['qualified_contracts']),output=str(args.output))))
