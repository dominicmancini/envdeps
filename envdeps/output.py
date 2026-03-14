from loguru import logger
from packaging.requirements import Requirement
from packaging.specifiers import Specifier

import envdeps.pkgs as pkgs

# type Dependencies = dict[str, Requirement]


def check_req(req: Requirement, deps: dict[str, pkgs.PkgInfo]):
    norm_reqname = pkgs.normalize(req.name)
    if norm_reqname not in deps:
        logger.error(f"Could not find req: {norm_reqname} in deps: {deps.keys()}")
        return False
    req_pkginfo = deps[norm_reqname]
    if not req.specifier:
        logger.info(f"No specifier for req: {req}. Returning True")
        return True
    valid_spec = req.specifier.contains(req_pkginfo.version)
    if not valid_spec:
        logger.warning("")

    if norm_reqname in deps:
        req_pkginfo = deps[norm_reqname]
        if req.specifier:
            valid = req.specifier.contains(req_pkginfo.version)


def format_reqs(deps: list[pkgs.PkgInfo], mode: str):
    lines = []
    for pkg in deps:
        line = f"{pkg.dist.name}"
        if mode != "":
            spec = Specifier(f"{mode}{pkg.version}")
            line = f"{line}{str(spec)}"
        lines.append(line)
    return lines


def format_line(dep: pkgs.PkgInfo, mode: str):
    line = f"{dep.dist.name}"
    if mode:
        line = line + f"{mode}{dep.version}"
    # line = mode == "" and dep.name or f"{dep.name}{mode}{dep.version}"
    return line


def update_reqs_alt(deps: dict[str, pkgs.PkgInfo], req_list: list[str], mode: str):
    # NOTE: `deps` is already filtered to only include the deps actually used in the
    # project based on imports. ALL of them need to be in the requirements.txt
    reqs = {pkgs.normalize(Requirement(i).name): Requirement(i) for i in req_list}
    dep_set = set(deps.keys())  # final list of dependencies to be used
    new_reqs = set(reqs.keys())
    new_reqs.update(dep_set)
    logger.info(f"`new_reqs`: After `update`: {new_reqs}")
    new_reqs.intersection_update(dep_set)
    logger.info(f"`new_reqs`: After `intersection_update`: {new_reqs}")
    final_reqs = []
    for name in new_reqs:
        if name in reqs:
            old_req = reqs[name]
            # Keep the existing req
            final_reqs.append(reqs[name])
        elif name in dep_set:
            # create req from new dependency
            final_reqs.append(Requirement(format_line(deps[name], mode)))
        else:
            logger.info(f"Hit `else` block during loop for req: {name}")
            # TODO: Figure out what should happen here
            pass
    return new_reqs


def update_reqs(req_lines: list[str], dep_list: list[pkgs.PkgInfo], mode: str):
    # TODO: Update reqs from new dependencies
    # reqs = [Requirement(req) for req in req_lines]
    req_names = set([pkgs.normalize(Requirement(i).name) for i in req_lines])
    dep_names = set([dep.name for dep in dep_list])
    print(f"Original Requirements: {req_names}")
    print(f"Scanned dependencies: {dep_names}", end="\n\n")
    # reqs = {pkgs.normalize(Requirement(i).name): Requirement(i) for i in req_lines}
    # deps = {p.name: p for p in dep_list}
    # to_remove: set[Requirement] = set()
    to_remove = req_names.difference(dep_names)
    to_add = dep_names.difference(req_names)
    print(f"Remove from requirements.txt: {to_remove}")
    print(f"Add to requirements.txt: {to_add}")

    # new_reqs = []
    # for dep in dep_list:
    #     if dep.name in req_names:
    #         pass
    #     else:
    #         new_reqs.append()

    # for rname, req in reqs.items():
    #     if rname in deps:
    #         pass


# def write_reqs(reqs_file: Path, deps: dict[str, PkgInfo], mode: str):
#     req_lines = []
