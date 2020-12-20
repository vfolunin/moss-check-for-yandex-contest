import mosspy, os.path, shutil, re, requests, zipfile

MOSS_ID = 12345


def extract_zip(zip_path, admins):
    print('Extracting archive ' + zip_path + '...')

    zip_dir = os.path.dirname(zip_path)

    work_dir = os.path.join(zip_dir, 'ANTIPLAGIARISM')
    os.mkdir(work_dir)

    archive_dir = os.path.join(work_dir, 'archive')
    os.mkdir(archive_dir)
    zipfile.ZipFile(zip_path, 'r').extractall(archive_dir)

    submission_ids = {}

    for sub_dir_name in os.listdir(archive_dir):
        user_name = sub_dir_name.split('-')[0]
        if user_name in admins:
            continue
        user_dir = os.path.join(archive_dir, sub_dir_name)
        for file_name in os.listdir(user_dir):
            problem_name, submission_id, *_, verdict = file_name.split('-')
            if verdict.startswith('OK'):
                problem_dir = os.path.join(work_dir, problem_name)
                if not os.path.isdir(problem_dir):
                    os.mkdir(problem_dir)
                source_file = os.path.join(user_dir, file_name)
                target_file = os.path.join(problem_dir, user_name + '.py')
                if not os.path.exists(target_file):
                    shutil.copyfile(source_file, target_file)
                    submission_ids[(user_name, problem_name)] = submission_id

    shutil.rmtree(archive_dir)
    return work_dir, submission_ids


def send_to_moss(problem_dir):
    print('Sending files from ' + problem_dir + ' to MOSS...')
    m = mosspy.Moss(MOSS_ID, 'python')
    m.addFilesByWildcard(problem_dir + '/*.py')
    m.setIgnoreLimit(4)
    return m.send()


def get_moss_results(moss_url, percent_limit):
    print('Parsing MOSS check results from ' + moss_url + '...')

    html = requests.get(moss_url).text.split('\n')
    regex = re.compile('match([\d]+)[\s\S]*?\/[A-Z]\/([\s\S]*?).py[\s\S]*?(\d+)%')

    matches = {}
    for row in html:
        if '/match' in row:
            match_index, user_name, percent = regex.search(row).group(1, 2, 3)
            if match_index not in matches:
                matches[match_index] = []
            matches[match_index].append((user_name.replace('_', ' '), int(percent)))

    plagiator_pairs = []
    for ((user_a, percent_a), (user_b, percent_b)) in matches.values():
        if percent_a >= percent_limit and percent_b >= percent_limit:
            plagiator_pairs.append((user_a, percent_a, user_b, percent_b))
    return plagiator_pairs


def get_submission_url(user_name, problem_name, submission_ids):
    return 'https://admin.contest.yandex.ru/submissions/' + submission_ids[(user_name, problem_name)]


def add_plagiarism_score(user_name, problem_name, plagiarism_score):
    if user_name not in plagiarism_score:
        plagiarism_score[user_name] = set()
    plagiarism_score[user_name].add(problem_name)


def process_problem(work_dir, problem_name, percent_limit, submission_ids, results, plagiarism_score):
    print('Processing problem ' + problem_name + '...')
    problem_dir = os.path.join(work_dir, problem_name)
    moss_url = send_to_moss(problem_dir)
    plagiator_pairs = get_moss_results(moss_url, percent_limit)
    for (user_a, percent_a, user_b, percent_b) in plagiator_pairs:
        add_plagiarism_score(user_a, problem_name, plagiarism_score)
        add_plagiarism_score(user_b, problem_name, plagiarism_score)
        url_a = get_submission_url(user_a, problem_name, submission_ids)
        url_b = get_submission_url(user_b, problem_name, submission_ids)
        results.append(problem_name)
        results.append('{} {} {}%'.format(user_a, url_a, percent_a))
        results.append('{} {} {}%'.format(user_b, url_b, percent_b))


def process_problems(work_dir, submission_ids, percent_limit):
    results, plagiarism_score = [], {}
    for problem_name in os.listdir(work_dir):
        process_problem(work_dir, problem_name, percent_limit, submission_ids, results, plagiarism_score)
    return results, plagiarism_score


def process_zip(zip_path, admins, percent_limit):
    work_dir, submission_ids = extract_zip(zip_path, admins)
    results, plagiarism_score = process_problems(work_dir, submission_ids, percent_limit)
    shutil.rmtree(work_dir)

    print('\n'.join(results), end='\n\n')
    for user_name in sorted(plagiarism_score.keys()):
        problem_names = ''.join(sorted(problem_name for problem_name in plagiarism_score[user_name]))
        print(user_name, problem_names)
