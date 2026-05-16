import 'package:flutter/material.dart';

import '../services/api_service.dart';
import '../ui/app_components.dart';
import '../ui/eduquest_theme.dart';
import 'login_screen.dart';

class AdminScreen extends StatefulWidget {
  final int userId;

  const AdminScreen({required this.userId, super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  static const _destinations = [
    ShellDestination(label: 'Overview', icon: Icons.dashboard_outlined),
    ShellDestination(label: 'Users', icon: Icons.group_outlined),
    ShellDestination(label: 'Safety', icon: Icons.shield_outlined),
    ShellDestination(label: 'Reports', icon: Icons.assessment_outlined),
    ShellDestination(label: 'Profile', icon: Icons.person_outline),
  ];

  int _selectedIndex = 0;
  List<dynamic> users = [];
  Map<String, dynamic>? platformStatus;
  bool isSafetyEnabled = true;
  bool retriesEnabled = true;
  bool isLoading = true;
  String? loadError;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      isLoading = true;
      loadError = null;
    });

    try {
      final usersData = await ApiService.getUsers();
      final statusData = await ApiService.getPlatformStatus();
      final configData = await ApiService.getSystemConfig();

      if (!mounted) return;

      setState(() {
        users = usersData;
        platformStatus = statusData;
        if (configData != null) {
          isSafetyEnabled = configData['ai_safety'] ?? true;
          retriesEnabled = configData['retries_enabled'] ?? true;
        }
        isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
        loadError = 'Admin workspace could not load governance data.';
      });
    }
  }

  Future<void> _updateConfig() async {
    final ok = await ApiService.updateSystemConfig(
      isSafetyEnabled,
      retriesEnabled,
      100,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          ok ? 'Configuration saved' : 'Failed to save configuration',
        ),
      ),
    );
    if (ok) {
      await _loadData();
    }
  }

  Future<void> _changeRole(int id, String currentRole) async {
    final newRole = await showAppModalSheet<String>(
      context: context,
      builder: (sheetContext) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Change role',
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Switch the governance role while keeping the mobile action flow stable.',
              style: Theme.of(sheetContext).textTheme.bodySmall,
            ),
            const SizedBox(height: 12),
            ...['student', 'teacher', 'admin'].map(
              (role) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: OutlinedButton(
                  onPressed: () => Navigator.of(sheetContext).pop(role),
                  child: Text(role.toUpperCase()),
                ),
              ),
            ),
          ],
        );
      },
    );
    if (newRole != null && newRole != currentRole) {
      await ApiService.changeUserRole(id, newRole);
      _loadData();
    }
  }

  Future<void> _toggleUserStatus(int id, bool currentStatus) async {
    await ApiService.toggleUserStatus(id, !currentStatus);
    _loadData();
  }

  Future<void> _logout() async {
    await ApiService.logout();
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        body: AppLoadingView(
          title: 'Loading admin workspace',
          message:
              'Syncing platform metrics, user controls, and policy settings.',
        ),
      );
    }

    if (loadError != null) {
      return Scaffold(
        body: AppErrorState(
          title: 'Admin workspace unavailable',
          description: loadError!,
          onRetry: _loadData,
        ),
      );
    }

    return EduQuestShell(
      title: 'Admin workspace',
      subtitle:
          'Govern platform usage, user access, and AI-related operating controls without desktop-style overflow.',
      currentIndex: _selectedIndex,
      destinations: _destinations,
      onSelect: (index) => setState(() => _selectedIndex = index),
      actions: [
        IconButton(
          tooltip: 'Refresh',
          onPressed: _loadData,
          icon: const Icon(Icons.refresh),
        ),
      ],
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: KeyedSubtree(
          key: ValueKey(_selectedIndex),
          child: _buildCurrentTab(),
        ),
      ),
    );
  }

  Widget _buildCurrentTab() {
    switch (_selectedIndex) {
      case 1:
        return _buildUsersTab();
      case 2:
        return _buildSafetyTab();
      case 3:
        return _buildReportsTab();
      case 4:
        return _buildProfileTab();
      default:
        return _buildOverviewTab();
    }
  }

  Widget _buildOverviewTab() {
    final metrics = platformStatus?['metrics'] as Map<String, dynamic>? ?? {};
    final services =
        platformStatus?['services'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final roleDistribution =
        platformStatus?['role_distribution'] as Map<String, dynamic>? ??
        <String, dynamic>{};

    return ListView(
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  const AppInfoChip(
                    label: 'Governance shell',
                    color: EduQuestColors.info,
                    icon: Icons.admin_panel_settings_outlined,
                  ),
                  AppInfoChip(
                    label:
                        'AI logs: ${platformStatus?['recent_ai_activity_count'] ?? 0}',
                    color: EduQuestColors.secondary,
                    icon: Icons.smart_toy_outlined,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                'Platform health overview',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Keep critical service, role, and policy signals visible without turning the mobile view into a cramped dashboard.',
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: Colors.white70),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Users',
              value: '${metrics['users'] ?? 0}',
              icon: Icons.people_outline,
              color: EduQuestColors.primary,
            ),
            AppStatCard(
              label: 'Courses',
              value: '${metrics['courses'] ?? 0}',
              icon: Icons.library_books_outlined,
              color: EduQuestColors.secondary,
            ),
            AppStatCard(
              label: 'Quizzes',
              value: '${metrics['quizzes'] ?? 0}',
              icon: Icons.quiz_outlined,
              color: EduQuestColors.info,
            ),
            AppStatCard(
              label: 'Attempts',
              value: '${metrics['attempts'] ?? 0}',
              icon: Icons.fact_check_outlined,
              color: EduQuestColors.success,
            ),
          ],
        ),
        const SizedBox(height: 16),
        const AppSectionHeader(
          title: 'Service posture',
          subtitle:
              'A quick read on core services and policy-sensitive subsystems.',
        ),
        const SizedBox(height: 12),
        ...[
          (
            'AI Tutor policy',
            services['safety_filter']?.toString() ?? 'Unknown',
          ),
          ('Database', services['database']?.toString() ?? 'Unknown'),
          (
            'Role mix',
            'S ${roleDistribution['student'] ?? 0} • T ${roleDistribution['teacher'] ?? 0} • A ${roleDistribution['admin'] ?? 0}',
          ),
        ].map(
          (entry) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: AppSurface(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    entry.$1,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(entry.$2, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUsersTab() {
    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Users and roles',
          subtitle: 'Inspect account status, change roles, and control access.',
        ),
        const SizedBox(height: 12),
        if (users.isEmpty)
          const AppEmptyState(
            icon: Icons.group_outlined,
            title: 'No users returned',
            description:
                'User governance data should populate here from the admin endpoint.',
          )
        else
          ...users.map((user) {
            final isActive = user['is_active'] ?? true;
            final role = user['role']?.toString() ?? 'student';
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: AppSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          backgroundColor:
                              isActive
                                  ? EduQuestColors.primarySoft
                                  : EduQuestColors.danger.withValues(
                                    alpha: 0.16,
                                  ),
                          child: Icon(
                            role == 'teacher'
                                ? Icons.school_outlined
                                : role == 'admin'
                                ? Icons.admin_panel_settings_outlined
                                : Icons.person_outline,
                            color:
                                isActive
                                    ? EduQuestColors.primary
                                    : EduQuestColors.danger,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                user['name']?.toString() ??
                                    user['email']?.toString() ??
                                    'User',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                user['email']?.toString() ?? '',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        AppInfoChip(
                          label: role.toUpperCase(),
                          color: EduQuestColors.info,
                        ),
                        AppInfoChip(
                          label: isActive ? 'Active' : 'Suspended',
                          color:
                              isActive
                                  ? EduQuestColors.success
                                  : EduQuestColors.danger,
                        ),
                        AppInfoChip(
                          label: '${user['xp'] ?? 0} XP',
                          color: EduQuestColors.secondary,
                        ),
                        AppInfoChip(
                          label:
                              'Lvl ${user['level'] ?? 1} • ${user['streak'] ?? 0}d',
                          color: EduQuestColors.primary,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    AdaptiveTwoPane(
                      first: OutlinedButton(
                        onPressed: () => _changeRole(user['id'], role),
                        child: const Text('Change role'),
                      ),
                      second: ElevatedButton(
                        onPressed:
                            () => _toggleUserStatus(user['id'], isActive),
                        style: ElevatedButton.styleFrom(
                          backgroundColor:
                              isActive
                                  ? EduQuestColors.danger
                                  : EduQuestColors.success,
                        ),
                        child: Text(isActive ? 'Disable' : 'Enable'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  Widget _buildSafetyTab() {
    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Safety and policy controls',
          subtitle: 'Tune AI filtering, retries, and motivational parameters.',
        ),
        const SizedBox(height: 12),
        AppSurface(
          child: Column(
            children: [
              SwitchListTile(
                title: const Text('Strict AI safety filter'),
                subtitle: const Text(
                  'Prevent AI from answering unsafe or off-topic requests.',
                ),
                value: isSafetyEnabled,
                onChanged: (value) {
                  setState(() => isSafetyEnabled = value);
                  _updateConfig();
                },
              ),
              const Divider(),
              SwitchListTile(
                title: const Text('Allow quiz retries'),
                subtitle: const Text(
                  'Support low-stakes mastery through repeated attempts.',
                ),
                value: retriesEnabled,
                onChanged: (value) {
                  setState(() => retriesEnabled = value);
                  _updateConfig();
                },
              ),
              const Divider(),
              const AppStatusBanner(
                message:
                    'Quiz XP is managed by teachers on each quiz. Admin safety settings no longer control assessment rewards.',
                color: EduQuestColors.info,
                icon: Icons.info_outline,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildReportsTab() {
    final metrics = platformStatus?['metrics'] as Map<String, dynamic>? ?? {};
    final roleDistribution =
        platformStatus?['role_distribution'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final activeCounts =
        platformStatus?['active_vs_inactive_users'] as Map<String, dynamic>? ??
        <String, dynamic>{};
    final configSnapshot =
        platformStatus?['config_snapshot'] as Map<String, dynamic>? ??
        <String, dynamic>{};

    return ListView(
      children: [
        const AppSectionHeader(
          title: 'Platform reports',
          subtitle:
              'Aggregated signals for audit-style readouts and operating awareness.',
        ),
        const SizedBox(height: 12),
        ResponsiveStatsGrid(
          children: [
            AppStatCard(
              label: 'Active users',
              value: '${activeCounts['active'] ?? 0}',
              icon: Icons.person_pin_circle_outlined,
              color: EduQuestColors.success,
            ),
            AppStatCard(
              label: 'Inactive users',
              value: '${activeCounts['inactive'] ?? 0}',
              icon: Icons.person_off_outlined,
              color: EduQuestColors.danger,
            ),
            AppStatCard(
              label: 'AI activity',
              value: '${platformStatus?['recent_ai_activity_count'] ?? 0}',
              icon: Icons.smart_toy_outlined,
              color: EduQuestColors.info,
            ),
            AppStatCard(
              label: 'Lessons',
              value: '${metrics['lessons'] ?? 0}',
              icon: Icons.view_list_outlined,
              color: EduQuestColors.secondary,
            ),
          ],
        ),
        const SizedBox(height: 16),
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Role distribution',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  AppInfoChip(
                    label: 'Students ${roleDistribution['student'] ?? 0}',
                    color: EduQuestColors.primary,
                  ),
                  AppInfoChip(
                    label: 'Teachers ${roleDistribution['teacher'] ?? 0}',
                    color: EduQuestColors.info,
                  ),
                  AppInfoChip(
                    label: 'Admins ${roleDistribution['admin'] ?? 0}',
                    color: EduQuestColors.secondary,
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                'Policy snapshot',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 10),
              ...[
                'AI safety: ${configSnapshot['ai_safety'] == true ? 'Enabled' : 'Disabled'}',
                'Retries: ${configSnapshot['retries_enabled'] == true ? 'Enabled' : 'Disabled'}',
                'Quiz XP: Teacher-managed per quiz',
                'Attempts logged: ${metrics['attempts'] ?? 0}',
              ].map(
                (line) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    line,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildProfileTab() {
    return ListView(
      children: [
        AppSurface(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: EduQuestColors.primarySoft,
                    child: const Icon(Icons.admin_panel_settings_outlined),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Administrator account',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Role-aware governance shell for users, safety controls, and platform reports.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  const AppInfoChip(label: 'Admin', color: EduQuestColors.info),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        AppActionCard(
          title: 'Refresh workspace',
          subtitle: 'Reload users, platform health, and current configuration.',
          icon: Icons.refresh_outlined,
          color: EduQuestColors.info,
          onTap: _loadData,
        ),
        const SizedBox(height: 12),
        AppActionCard(
          title: 'Sign out',
          subtitle: 'Exit the admin role and return to the shared auth entry.',
          icon: Icons.logout_outlined,
          color: EduQuestColors.danger,
          onTap: _logout,
        ),
      ],
    );
  }
}
