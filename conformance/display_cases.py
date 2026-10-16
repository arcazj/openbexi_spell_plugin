"""Independent native display scenarios, with all four qualification dimensions."""
CASES = {}


def family(name, **dimensions):
    assert set(dimensions) == {'positive', 'boundary', 'failure', 'encoding'}
    for dimension, source in dimensions.items():
        CASES[name + ':' + dimension] = dict(dimension=dimension, family=name, source=source)


family('lifecycle',
    positive="""good_default(OpenDisplay, ALPHA)
app=one_app();equal(app['host'],'DSS');equal(app['monitor'],1)
equal(set(app['displays']),{ALPHA})
good_default(CloseDisplay, ALPHA);equal(apps(),{})
""",
    boundary="""good(OpenDisplay, ALPHA)
good(OpenDisplay, ALPHA);equal(len(apps()),1)
good(CloseDisplay, ALPHA)
bad(CloseDisplay, ALPHA)
good(OpenDisplay, ALPHA);good(CloseDisplay, ALPHA)
""",
    failure="""bad(OpenDisplay, 'missing')
bad(OpenDisplay, 42)
bad(CloseDisplay, 'missing')
good(OpenDisplay, ALPHA);good(CloseDisplay, ALPHA);equal(apps(),{})
""",
    encoding="""good(OpenDisplay, UNICODE_ALPHA)
equal(set(one_app()['displays']),{UNICODE_ALPHA})
web=fixture('viewer');assert UNICODE_ALPHA in web['html']
assert 'TM.CORE.TICK' in web['html']
good(CloseDisplay, UNICODE_ALPHA);equal(apps(),{})
""")

family('workspace',
    positive="""good(OpenWorkspace, WORKSPACE)
app=one_app();equal(set(app['displays']),{ALPHA,PLOT})
equal(app['workspaces'],{WORKSPACE:[ALPHA,PLOT]})
good(CloseWorkspace, WORKSPACE);equal(apps(),{})
""",
    boundary="""good(OpenDisplay, UNICODE_ALPHA)
good(OpenWorkspace, WORKSPACE, Reuse=True)
equal(len(apps()),1);equal(len(one_app()['displays']),3)
good(CloseWorkspace, WORKSPACE)
equal(set(one_app()['displays']),{UNICODE_ALPHA})
good(OpenWorkspace, WORKSPACE, Reuse=False);equal(len(apps()),2)
good(CloseWorkspace, WORKSPACE);good(CloseDisplay,UNICODE_ALPHA);equal(apps(),{})
""",
    failure="""bad(OpenWorkspace, 'missing')
bad(OpenWorkspace, 0)
bad(CloseWorkspace, WORKSPACE)
good(OpenWorkspace, WORKSPACE)
bad(PrintDisplay, WORKSPACE)
good(CloseWorkspace, WORKSPACE);equal(apps(),{})
""",
    encoding="""good(OpenWorkspace, UNICODE_WORKSPACE)
app=one_app();equal(app['workspaces'],{UNICODE_WORKSPACE:[UNICODE_ALPHA,PLOT]})
web=fixture('viewer');assert UNICODE_ALPHA in web['html'] and '<svg ' in web['html']
good(CloseWorkspace, UNICODE_WORKSPACE);equal(apps(),{})
""")

family('routing',
    positive="""good(OpenDisplay, ALPHA, Host='DSS_AUX', Monitor=2)
good(OpenWorkspace, WORKSPACE, Host='DSS', Monitor=1)
equal(sorted((app['host'],app['monitor']) for app in apps().values()),[('DSS',1),('DSS_AUX',2)])
good(CloseWorkspace, WORKSPACE, Host='DSS')
equal(one_app()['host'],'DSS_AUX')
good(CloseDisplay, ALPHA, Host='DSS_AUX');equal(apps(),{})
""",
    boundary="""for host in ('DSS','DSS_AUX'):
    for monitor in (1,2):good(OpenWorkspace,WORKSPACE,Host=host,Monitor=monitor)
equal(len(apps()),4)
good(CloseWorkspace,WORKSPACE,Host='DSS');equal(len(apps()),2)
good(CloseWorkspace,WORKSPACE,Host='DSS_AUX');equal(apps(),{})
""",
    failure="""for function,target in ((OpenDisplay,ALPHA),(OpenWorkspace,WORKSPACE)):
    for options in ({Host:'missing'},{Monitor:True},{Monitor:0},{Monitor:3},{Monitor:'1'}):
        bad(function,target,**options)
good(OpenDisplay,ALPHA,Host='DSS_AUX',Monitor=2)
bad(CloseDisplay,ALPHA,Host='DSS')
good(CloseDisplay,ALPHA,Host='DSS_AUX');equal(apps(),{})
""",
    encoding="""good(OpenWorkspace,UNICODE_WORKSPACE,Host='DSS_AUX',Monitor=2)
app=one_app();equal((app['host'],app['monitor']),('DSS_AUX',2))
equal(set(app['displays']),{UNICODE_ALPHA,PLOT})
good(CloseWorkspace,UNICODE_WORKSPACE,Host='DSS_AUX');equal(apps(),{})
""")

family('reuse',
    positive="""good(OpenDisplay,ALPHA,Reuse=False)
first=one_app()['id']
good(OpenDisplay,PLOT,Reuse=True);equal(one_app()['id'],first)
good(OpenWorkspace,WORKSPACE,Reuse=False);equal(len(apps()),2)
good(OpenWorkspace,WORKSPACE,Reuse=True);equal(len(apps()),2)
good(CloseWorkspace,WORKSPACE)
good(CloseDisplay,ALPHA);good(CloseDisplay,PLOT);equal(apps(),{})
""",
    boundary="""for index in range(16):good(OpenDisplay,ALPHA,Reuse=False)
equal(len(apps()),16)
bad(OpenDisplay,ALPHA,Reuse=False)
good(OpenDisplay,PLOT,Reuse=True)
equal(set(apps()['16']['displays']),{ALPHA,PLOT})
good(CloseDisplay,ALPHA);equal(len(apps()),1)
good(CloseDisplay,PLOT);equal(apps(),{})
""",
    failure="""for value in (0,1,'False',None):
    bad(OpenDisplay,ALPHA,Reuse=value)
    bad(OpenWorkspace,WORKSPACE,Reuse=value)
good(OpenWorkspace,WORKSPACE,Reuse=False)
good(CloseWorkspace,WORKSPACE);equal(apps(),{})
""",
    encoding="""good(OpenDisplay,UNICODE_ALPHA,Reuse=False)
good(OpenWorkspace,UNICODE_WORKSPACE,Reuse=True)
equal(len(apps()),1);equal(set(one_app()['displays']),{UNICODE_ALPHA,PLOT})
good(OpenWorkspace,UNICODE_WORKSPACE,Reuse=False);equal(len(apps()),2)
good(CloseWorkspace,UNICODE_WORKSPACE);equal(apps(),{})
""")

family('timespan',
    positive="""good(OpenDisplay,PLOT,Time=1*HOUR)
equal(one_app()['displays'][PLOT]['span_seconds'],3600)
plot_axis(3600)
good(PrintDisplay,PLOT,Format=PS)
job=last_job();equal(job['span_seconds'],3600)
assert 'Initial time span: 3600.000000 seconds' in job['content']
good(CloseDisplay,PLOT)
""",
    boundary="""for span in (.25,86400):
    good(OpenDisplay,PLOT,Time=span)
    equal(one_app()['displays'][PLOT]['span_seconds'],span);plot_axis(span)
good(CloseDisplay,PLOT);equal(apps(),{})
""",
    failure="""for span in (0,-1,True,86401,TIME('2026/01/01 00:00:00')):
    bad(OpenDisplay,PLOT,Time=span)
bad(OpenDisplay,ALPHA,Time=1)
good(OpenDisplay,PLOT,Time=1);good(CloseDisplay,PLOT);equal(apps(),{})
""",
    encoding="""good(OpenDisplay,PLOT,Time=TIME('+00:00:01.125'))
equal(one_app()['displays'][PLOT]['span_seconds'],1.125);plot_axis(1.125)
good(OpenDisplay,PLOT,Time=TIME('+01:00:00'),Reuse=True)
equal(one_app()['displays'][PLOT]['span_seconds'],3600)
good(CloseDisplay,PLOT);equal(apps(),{})
""")

family('printing',
    positive="""equal((PS,VECTOR),('PS','VECTOR'))
good(OpenDisplay,ALPHA)
for fmt in (PS,VECTOR):
    if fmt==PS:good_default(PrintDisplay,ALPHA)
    else:good(PrintDisplay,ALPHA,Format=fmt)
    print_document(last_job(),fmt,False)
good(CloseDisplay,ALPHA)
""",
    boundary="""good(OpenDisplay,ALPHA)
good(PrintDisplay,ALPHA);print_document(last_job(),PS,False)
good(PrintDisplay,ALPHA,Format='vector',Printer='');print_document(last_job(),VECTOR,False)
for index in range(62):good(PrintDisplay,ALPHA,Format=VECTOR)
equal(len(mark()['ground']['display_jobs']),64)
bad(PrintDisplay,ALPHA,Format=VECTOR)
good(CloseDisplay,ALPHA)
""",
    failure="""bad(PrintDisplay,ALPHA)
good(OpenDisplay,ALPHA)
bad(PrintDisplay,ALPHA,Format='PDF')
bad(PrintDisplay,ALPHA,Format=0)
good(OpenDisplay,PLOT);bad(PrintDisplay,PLOT,Format=VECTOR)
good(OpenWorkspace,WORKSPACE);bad(PrintDisplay,WORKSPACE)
good(PrintDisplay,ALPHA,Format=PS);print_document(last_job(),PS,False)
good(CloseWorkspace,WORKSPACE)
""",
    encoding="""good(OpenDisplay,UNICODE_ALPHA)
for fmt in (PS,VECTOR):
    good(PrintDisplay,UNICODE_ALPHA,Format=fmt)
    job=last_job();equal(job['display'],UNICODE_ALPHA);assert job['content'].isascii()
    print_document(job,fmt,False)
assert r'Telemetr\\xeda' in last_job()['content']
good(CloseDisplay,UNICODE_ALPHA)
""")

family('printer',
    positive="""good(OpenDisplay,ALPHA)
good(PrintDisplay,ALPHA,Printer='DSS_REPORTS')
print_document(last_job(),PS,True)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
web=fixture('viewer');assert '/jobs/1' in web['html']
good(CloseDisplay,ALPHA)
""",
    boundary="""good(OpenDisplay,ALPHA,Host='DSS_AUX')
for fmt in (PS,VECTOR):
    good(PrintDisplay,ALPHA,Host='DSS_AUX',Printer='DSS_REPORTS',Format=fmt)
    job=last_job();equal(job['host'],'DSS_AUX');print_document(job,fmt,True)
good(CloseDisplay,ALPHA,Host='DSS_AUX');equal(apps(),{})
""",
    failure="""good(OpenDisplay,ALPHA)
for printer in ('missing',42,None):bad(PrintDisplay,ALPHA,Printer=printer)
bad(PrintDisplay,ALPHA,Host='DSS_AUX',Printer='DSS_REPORTS')
good(PrintDisplay,ALPHA,Printer='DSS_REPORTS');print_document(last_job(),PS,True)
good(CloseDisplay,ALPHA)
""",
    encoding="""good(OpenWorkspace,UNICODE_WORKSPACE,Host='DSS_AUX')
for fmt in (PS,VECTOR):
    good(PrintDisplay,UNICODE_ALPHA,Host='DSS_AUX',Printer='DSS_REPORTS',Format=fmt)
    job=last_job();equal(job['display'],UNICODE_ALPHA);print_document(job,fmt,True)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(CloseWorkspace,UNICODE_WORKSPACE,Host='DSS_AUX');equal(apps(),{})
""")

# Encoding is additional coverage. These separate recovery scenarios retain a
# rejected call, reopen the real persistent driver, and complete valid operations.
RECOVERY = {
    'lifecycle': """bad(CloseDisplay,ALPHA)
fixture('reopen')
good(OpenDisplay,UNICODE_ALPHA);good(CloseDisplay,UNICODE_ALPHA);equal(apps(),{})
""",
    'workspace': """bad(OpenWorkspace,'missing')
good(OpenWorkspace,UNICODE_WORKSPACE)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(CloseWorkspace,UNICODE_WORKSPACE)
bad(CloseWorkspace,UNICODE_WORKSPACE)
good(OpenWorkspace,WORKSPACE);good(CloseWorkspace,WORKSPACE);equal(apps(),{})
""",
    'routing': """good(OpenWorkspace,WORKSPACE,Host='DSS_AUX',Monitor=2)
bad(CloseWorkspace,WORKSPACE,Host='DSS')
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(CloseWorkspace,WORKSPACE,Host='DSS_AUX')
good(OpenWorkspace,WORKSPACE,Host='DSS',Monitor=1)
equal((one_app()['host'],one_app()['monitor']),('DSS',1))
good(CloseWorkspace,WORKSPACE,Host='DSS');equal(apps(),{})
""",
    'reuse': """good(OpenDisplay,ALPHA,Reuse=False)
bad(OpenDisplay,UNICODE_ALPHA,Reuse=1)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(OpenDisplay,UNICODE_ALPHA,Reuse=True)
equal(len(apps()),1);equal(set(one_app()['displays']),{ALPHA,UNICODE_ALPHA})
good(CloseDisplay,ALPHA);good(CloseDisplay,UNICODE_ALPHA);equal(apps(),{})
""",
    'timespan': """good(OpenDisplay,PLOT,Time=.25)
bad(OpenDisplay,PLOT,Time=0)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(OpenDisplay,PLOT,Time=HOUR,Reuse=True)
equal(one_app()['displays'][PLOT]['span_seconds'],3600);plot_axis(3600)
good(CloseDisplay,PLOT);equal(apps(),{})
""",
    'printing': """good(OpenDisplay,UNICODE_ALPHA)
bad(PrintDisplay,UNICODE_ALPHA,Format='PDF')
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
for fmt in (PS,VECTOR):
    good(PrintDisplay,UNICODE_ALPHA,Format=fmt);print_document(last_job(),fmt,False)
good(CloseDisplay,UNICODE_ALPHA);equal(apps(),{})
""",
    'printer': """good(OpenDisplay,UNICODE_ALPHA,Host='DSS_AUX')
bad(PrintDisplay,UNICODE_ALPHA,Host='DSS_AUX',Printer='missing')
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
for fmt in (PS,VECTOR):
    good(PrintDisplay,UNICODE_ALPHA,Host='DSS_AUX',Printer='DSS_REPORTS',Format=fmt)
    print_document(last_job(),fmt,True)
before=mark();after=fixture('reopen');equal(before['ground'],after['ground'])
good(CloseDisplay,UNICODE_ALPHA,Host='DSS_AUX');equal(apps(),{})
""",
}
assert set(RECOVERY) == {row['family'] for row in CASES.values()}
for name, source in RECOVERY.items():
    CASES[name + ':recovery'] = dict(dimension='recovery', family=name, source=source)
