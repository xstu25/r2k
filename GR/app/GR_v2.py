import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import threading
from datetime import datetime
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import traceback
import json
import re
import os
from PIL import Image
import os
import webbrowser
from datetime import datetime


class RaceDataScraper:
    def __init__(self):
        print("Initialisation du scraper...")
        self.chrome_options = Options()
        self.chrome_options.add_argument('--start-maximized')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')

        # Ajout du dictionnaire de correspondance des courses
        self.race_names = {
            "MAS": "Mascareignes",
            "GRR": "Diagonale des Fous",
            "TDB": "Trail de Bourbon",
            "MTR": "Métiss Trail",
            "ZEM": "Zembrocal"
        }

        print("Installation du ChromeDriver...")
        self.service = Service(ChromeDriverManager().install())
        self.driver = None
        self.all_data = {}
        self.load_data()

    def get_race_from_url(self, driver):
        """Récupère le code de la course depuis l'URL"""
        try:
            # Attendre que l'URL soit mise à jour avec le raceId avec un timeout plus court
            # time.sleep(1)
            current_url = driver.current_url
            print(f"URL courante: {current_url}")

            # Chercher le paramètre raceId
            match = re.search(r'raceId=(\w+)', current_url)
            if match:
                race_code = match.group(1)
                race_name = self.race_names.get(race_code, "Course inconnue")
                print(f"Course trouvée: {race_name} ({race_code})")
                return race_name
            else:
                # Si pas de raceId dans l'URL, on peut essayer de déduire la course
                # depuis les informations de la page
                try:
                    race_info = driver.find_element(By.CLASS_NAME, "mui-oah8u0").text
                    for code, name in self.race_names.items():
                        if name.lower() in race_info.lower():
                            return name
                except:
                    pass
                print("Code course non trouvé dans l'URL")
                return "Course inconnue"
        except Exception as e:
            print(f"Erreur lors de la récupération du nom de la course: {e}")
            return "Course inconnue"

    def load_data(self):
        try:
            if os.path.exists('race_data.json'):
                with open('race_data.json', 'r', encoding='utf-8') as f:
                    self.all_data = json.load(f)
                print(f"Données chargées pour {len(self.all_data)} coureurs")
        except Exception as e:
            print(f"Erreur lors du chargement des données: {e}")
            self.all_data = {}

    def save_data(self):
        try:
            with open('race_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, ensure_ascii=False, indent=4)
            print("Données sauvegardées avec succès")
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des données: {e}")

    def initialize_driver(self):
        if not self.driver:
            self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
        return self.driver

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def extract_numeric_value(self, text):
        """Extrait la valeur numérique d'une chaîne de caractères"""
        if not text:
            return 0
        match = re.search(r'(-?\d+(?:\.\d+)?)', text.replace(',', '.'))
        return float(match.group(1)) if match else 0

    def extract_rank_info(self, element):
        """Extrait le classement et l'évolution du classement"""
        try:
            rank_text = element.find_element(By.CLASS_NAME, "mui-n2g1ua").text
            rank = int(rank_text)

            # Tenter d'extraire l'évolution du classement
            try:
                evolution_element = element.find_element(By.CLASS_NAME, "mui-1duggqj")
                evolution_text = evolution_element.text
                evolution = int(re.findall(r'[-+]?\d+', evolution_text)[0])
            except:
                evolution = 0

            return rank, evolution
        except:
            return None, None

    def get_checkpoint_data(self, driver):
        """Extraire les données des points de passage pour un coureur"""
        try:
            checkpoints = []
            rows = driver.find_elements(By.CLASS_NAME, "MuiTableRow-root")

            for row in rows:
                try:
                    cells = row.find_elements(By.CLASS_NAME, "MuiTableCell-root")
                    if len(cells) < 7:
                        continue

                    # Extraction du nom du point de passage
                    try:
                        point_name = row.find_element(By.CLASS_NAME, "mui-1v8uc0v").text.strip()
                    except:
                        continue

                    # Extraction du kilomètre
                    try:
                        km_element = row.find_elements(By.CLASS_NAME, "mui-o6szkf")[0]
                        kilometer = self.extract_numeric_value(km_element.text)
                    except:
                        kilometer = 0

                    # Extraction du temps de passage (première cellule mui-1g6ia2u)
                    try:
                        passage_time = row.find_element(By.CLASS_NAME, "mui-1g6ia2u").text.strip()
                    except:
                        passage_time = "N/A"

                    # Extraction du temps de course (modification)
                    try:
                        # Trouver toutes les cellules qui pourraient contenir le temps de course
                        time_cells = cells[4].find_elements(By.CLASS_NAME, "mui-193t7sq")
                        # Prendre le premier élément qui est directement dans la cellule
                        # (pas dans une structure imbriquée avec temps de repos)
                        race_time = None
                        for time_cell in time_cells:
                            # Vérifier si l'élément parent n'a pas la classe mui-1jkxyqi
                            # (qui est utilisée pour le temps de repos)
                            parent = time_cell.find_element(By.XPATH, "..")
                            if "mui-1jkxyqi" not in parent.get_attribute("class"):
                                race_time = time_cell.text.strip()
                                break

                        if not race_time:
                            race_time = "N/A"
                    except:
                        race_time = "N/A"

                    # Modification de l'extraction de la vitesse
                    try:
                        speed_cells = row.find_elements(By.CLASS_NAME, "mui-193t7sq")
                        speed = "N/A"
                        for cell in speed_cells:
                            cell_text = cell.text.strip()
                            if 'km/h' in cell_text:  # Vérifie si c'est bien une vitesse
                                speed = cell_text
                                break

                        # Récupération de la vitesse effort
                        effort_containers = row.find_elements(By.CLASS_NAME, "mui-1jkxyqi")
                        effort_speed = "N/A"
                        for container in effort_containers:
                            if "Vitesse effort" in container.text:
                                effort_speed_element = container.find_element(By.CLASS_NAME, "mui-vm42pa")
                                effort_speed = effort_speed_element.text.strip()
                                break
                    except Exception as e:
                        print(f"Erreur lors de l'extraction de la vitesse: {e}")
                        speed = "N/A"
                        effort_speed = "N/A"

                        # Extraction du dénivelé positif et négatif
                    try:
                        elevation_cells = row.find_elements(By.CLASS_NAME, "mui-vm42pa")
                        if len(elevation_cells) >= 2:
                            d_plus_text = elevation_cells[-2].text
                            d_minus_text = elevation_cells[-1].text

                            # Extraction des valeurs numériques sans les signes + ou -
                            d_plus = int(re.search(r'\d+', d_plus_text).group()) if re.search(r'\d+',
                                                                                              d_plus_text) else 0
                            d_minus = int(re.search(r'\d+', d_minus_text).group()) if re.search(r'\d+',
                                                                                                d_minus_text) else 0
                        else:
                            d_plus = 0
                            d_minus = 0
                    except:
                        d_plus = 0
                        d_minus = 0

                        # Extraction du classement et de son évolution
                    try:
                        rank_cells = row.find_elements(By.CLASS_NAME, "mui-ct9q29")
                        rank = None
                        evolution = None

                        for cell in rank_cells:
                            try:
                                # Extraction du classement
                                rank = cell.find_element(By.CLASS_NAME, "mui-n2g1ua").text.strip()

                                # Tentative d'extraction de l'évolution (positive ou négative)
                                try:
                                    evolution_element = None
                                    for class_name in ["mui-2e3q6l", "mui-1duggqj"]:
                                        try:
                                            evolution_element = cell.find_element(By.CLASS_NAME, class_name)
                                            break
                                        except:
                                            continue

                                    if evolution_element:
                                        evolution_text = evolution_element.text.strip()
                                        evolution_match = re.search(r'[+-]?\d+',
                                                                    evolution_text.replace('(', '').replace(')', ''))
                                        if evolution_match:
                                            evolution = int(evolution_match.group())
                                except:
                                    evolution = None
                                break
                            except:
                                continue
                    except Exception as e:
                        print(f"Erreur lors de l'extraction du classement: {e}")
                        rank = None
                        evolution = None

                    checkpoint = {
                        'point': point_name,
                        'kilometer': kilometer,
                        'passage_time': passage_time,
                        'race_time': race_time,
                        'speed': speed,
                        'effort_speed': effort_speed,
                        'elevation_gain': d_plus,
                        'elevation_loss': d_minus,
                        'rank': rank,
                        'rank_evolution': evolution
                    }
                    checkpoints.append(checkpoint)

                except Exception as e:
                    print(f"Erreur lors du traitement d'un point de passage: {e}")
                    continue

            return checkpoints

        except Exception as e:
            print(f"Erreur lors de l'extraction des points de passage: {e}")
            traceback.print_exc()
            return []

    def normalize_text(self, text):
        """Normalise le texte pour la comparaison (supprime accents et met en minuscules)"""
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                       if unicodedata.category(c) != 'Mn')

    def get_runner_data(self, bib_number):
        """Récupère les données complètes d'un coureur"""
        bib_str = str(bib_number)
        print(f"\nTraitement du dossard {bib_number}")

        # Vérifier si les données sont en cache
        if bib_str in self.all_data:
            print(f"Données trouvées en cache pour le dossard {bib_number}")
            return self.all_data[bib_str]

        print(f"Récupération des données en ligne pour le dossard {bib_number}")
        try:
            # Initialisation du driver et chargement de la page
            driver = self.initialize_driver()
            url = f"https://grandraid-reunion-oxybol.v3.livetrail.net/fr/2024/runners/{bib_number}"
            driver.get(url)
            time.sleep(1)

            # Initialisation des variables par défaut
            name = "Inconnu"
            category = "Inconnue"
            avg_speed = "N/A"
            state = "Inconnu"
            finish_time = "-"
            rankings = {"Général": "", "Sexe": "", "Catégorie": ""}

            # Récupération du nom de la course
            race_name = self.get_race_from_url(driver)

            # Récupération du nom du coureur
            try:
                name_element = driver.find_element(By.CLASS_NAME, "mui-oah8u0")
                name = name_element.text.strip()
            except:
                print(f"Erreur lors de la récupération du nom pour le dossard {bib_number}")

            # Récupération de la catégorie
            try:
                category_element = driver.find_element(By.CLASS_NAME, "mui-1vu7he5")
                category = category_element.text.strip()
            except:
                print(f"Erreur lors de la récupération de la catégorie pour le dossard {bib_number}")

            # Récupération de l'état et du temps
            try:
                print("Recherche de l'état du coureur...")
                raw_state = "Inconnu"

                # Chercher Finisher
                try:
                    state_container = driver.find_element(By.CLASS_NAME, "mui-w9oezj")
                    state_element = state_container.find_element(By.CSS_SELECTOR, "p.MuiTypography-noWrap")
                    raw_state = state_element.text.strip()
                    print(f"État trouvé dans mui-w9oezj: {raw_state}")
                except:
                    # Chercher Abandon ou Non partant
                    try:
                        state_container = driver.find_element(By.CLASS_NAME, "mui-gzldy9")
                        try:
                            state_element = state_container.find_element(By.CLASS_NAME, "mui-1xavr8a")
                            raw_state = state_element.text.strip()
                            print(f"État trouvé dans mui-gzldy9 (abandon): {raw_state}")
                        except:
                            state_element = state_container.find_element(By.CLASS_NAME, "mui-evvpi6")
                            raw_state = state_element.text.strip()
                            print(f"État trouvé dans mui-gzldy9 (non partant): {raw_state}")
                    except:
                        print("Aucun état trouvé dans les conteneurs connus")

                print(f"État brut trouvé: {raw_state}")
                normalized_state = raw_state.upper()

                # Traitement des non partants
                if "NON PARTANT" in normalized_state:
                    runner_data = {
                        'infos': {
                            'bib_number': bib_number,
                            'race_name': race_name,
                            'name': name,
                            'category': category,
                            'state': "Non partant",
                            'finish_time': "-",
                            'overall_rank': "-",
                            'gender_rank': "-",
                            'category_rank': "-",
                            'average_speed': "-",
                            'last_checkpoint': "-",
                            'total_elevation_gain': 0,
                            'total_elevation_loss': 0
                        },
                        'checkpoints': []
                    }
                    self.all_data[bib_str] = runner_data
                    self.save_data()
                    return runner_data

                # Détermination de l'état et du temps pour les autres cas
                if "ABANDON" in normalized_state:
                    state = "Abandon"
                elif "FINISHER" in normalized_state:
                    state = "Finisher"
                else:
                    state = "En course"

                # Récupération du temps si disponible
                if state in ["Abandon", "Finisher"]:
                    try:
                        time_element = state_container.find_element(By.CLASS_NAME, "mui-1vazesu")
                        finish_time = time_element.text.strip()
                        if ':' in finish_time:
                            hours, minutes, _ = finish_time.split(':')
                            finish_time = f"{hours}h{minutes}"
                    except:
                        finish_time = "-"
                else:
                    finish_time = "En course"

                print(f"État normalisé: {state}")

                # Récupération de la vitesse moyenne si le coureur n'est pas non partant
                try:
                    print("\nDébut extraction vitesse moyenne...")
                    main_container = driver.find_element(By.CLASS_NAME, "mui-14iziq5")
                    print("Conteneur principal trouvé")

                    info_sections = main_container.find_elements(By.CLASS_NAME, "mui-157h3i3")
                    print(f"Nombre de sections info trouvées: {len(info_sections)}")

                    if len(info_sections) >= 2:
                        info_section = info_sections[1]
                        print("Section info de vitesse trouvée, recherche des éléments...")

                        for element in info_section.find_elements(By.CLASS_NAME, "mui-8v90jo"):
                            try:
                                label_container = element.find_element(By.CLASS_NAME, "mui-ct9q29")
                                label = label_container.find_element(By.CLASS_NAME, "mui-wenrje").text.strip()
                                print(f"Label trouvé: '{label}'")

                                if "VIT. MOY." in label.upper():
                                    print("Label de vitesse moyenne trouvé!")
                                    speed_value = element.find_elements(By.TAG_NAME, "p")[-1].text.strip()
                                    print(f"Valeur de vitesse trouvée: '{speed_value}'")
                                    avg_speed = speed_value
                                    break
                            except Exception as e:
                                print(f"Erreur lors de l'analyse d'un élément: {str(e)}")
                                continue
                except Exception as e:
                    print(f"Erreur lors de la récupération de la vitesse moyenne: {str(e)}")
                    avg_speed = "N/A"

                # Récupération des classements
                print("\nDébut récupération des classements")
                try:
                    print("Recherche des containers de classement...")
                    ranking_section = driver.find_element(By.CLASS_NAME, "mui-157h3i3")
                    rank_elements = ranking_section.find_elements(By.CLASS_NAME, "mui-4ae55t")
                    print(f"Nombre d'éléments de classement trouvés: {len(rank_elements)}")

                    for element in rank_elements:
                        try:
                            type_text = element.find_element(By.CLASS_NAME, "mui-280lq").text.strip().upper()
                            value_text = element.find_element(By.CLASS_NAME, "mui-17rj2i9").text.strip()
                            print(f"Trouvé: {type_text} = {value_text}")

                            if "GÉNÉRAL" in type_text or "GENERAL" in type_text:
                                rankings["Général"] = value_text
                            elif "SEXE" in type_text:
                                rankings["Sexe"] = value_text
                            elif "CATÉGORIE" in type_text or "CATEGORIE" in type_text:
                                rankings["Catégorie"] = value_text
                        except Exception as e:
                            print(f"Erreur lors de l'extraction d'un élément de classement: {str(e)}")

                    print("État final des classements:", rankings)
                except Exception as e:
                    print(f"Erreur lors de la récupération des classements: {str(e)}")

                # Récupération des points de passage
                checkpoints = self.get_checkpoint_data(driver)

                # Détermination du dernier point
                last_checkpoint = ""
                if checkpoints:
                    last_cp = checkpoints[-1]
                    last_checkpoint = last_cp['point']

                # Construction des données du coureur
                runner_data = {
                    'infos': {
                        'bib_number': bib_number,
                        'race_name': race_name,
                        'name': name,
                        'category': category,
                        'state': state,
                        'finish_time': finish_time,
                        'overall_rank': rankings['Général'],
                        'gender_rank': rankings['Sexe'],
                        'category_rank': rankings['Catégorie'],
                        'average_speed': avg_speed,
                        'last_checkpoint': last_checkpoint,
                        'total_elevation_gain': sum(cp['elevation_gain'] for cp in checkpoints) if checkpoints else 0,
                        'total_elevation_loss': sum(cp['elevation_loss'] for cp in checkpoints) if checkpoints else 0
                    },
                    'checkpoints': checkpoints
                }

                # Sauvegarde des données
                self.all_data[bib_str] = runner_data
                self.save_data()
                return runner_data

            except Exception as e:
                print(f"Erreur lors de la récupération de l'état: {str(e)}")
                state = "Inconnu"
                finish_time = "-"
                print("État inconnu assigné suite à une erreur")
                return None

        except Exception as e:
            print(f"Erreur générale pour le dossard {bib_number}: {str(e)}")
            traceback.print_exc()
            return None

class CheckpointWindow:
    def __init__(self, parent, bib_number, runner_data, checkpoint_data):
        self.window = ctk.CTkToplevel(parent)
        self.window.title(f"Détails du coureur {bib_number}")
        self.window.state('zoomed')  # Pour Windows

        # En-tête avec les informations du coureur
        header_frame = ctk.CTkFrame(self.window)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        # Diviser l'en-tête en deux colonnes
        left_info = ctk.CTkFrame(header_frame)
        left_info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        right_info = ctk.CTkFrame(header_frame)
        right_info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Informations coureur - Colonne gauche
        left_info_text = (
            f"Course: {runner_data['race_name']}\n"  # Ajout de la course
            f"Dossard: {bib_number}\n"
            f"Nom: {runner_data['name']}\n"
            f"Catégorie: {runner_data['category']}\n"
            f"État: {runner_data['state']}\n"
            f"Dernier point: {runner_data['last_checkpoint']}"
        )
        ctk.CTkLabel(left_info, text=left_info_text, justify="left").pack(padx=10, pady=10)

        # Informations coureur - Colonne droite
        right_info_text = (
            f"Classement général: {runner_data['overall_rank']}\n"
            f"Classement sexe: {runner_data['gender_rank']}\n"
            f"Classement catégorie: {runner_data['category_rank']}\n"
            f"Vitesse moyenne: {runner_data['average_speed']}\n"
            f"Dénivelé: {runner_data['total_elevation_gain']}m / {runner_data['total_elevation_loss']}m"
        )

        ctk.CTkLabel(right_info, text=right_info_text, justify="left").pack(padx=10, pady=10)

        # Configuration du style du tableau
        style = ttk.Style()
        style.configure(
            "Checkpoint.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b"
        )
        style.configure(
            "Checkpoint.Treeview.Heading",
            background="#2b2b2b",
            foreground="white"
        )

        # Tableau des points de passage
        tree_frame = ttk.Frame(self.window)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tableau des points de passage
        columns = (
            "point", "kilometer", "passage_time", "race_time", "speed", "effort_speed",  # Ajout de effort_speed
            "elevation_gain", "elevation_loss", "rank", "rank_evolution"
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Checkpoint.Treeview"
        )

        # Configuration des colonnes
        headers = {
            "point": "Point de passage",
            "kilometer": "KM",
            "passage_time": "Heure passage",
            "race_time": "Temps course",
            "speed": "Vitesse",
            "effort_speed": "Vitesse effort",
            "elevation_gain": "D+",
            "elevation_loss": "D-",
            "rank": "Class.",
            "rank_evolution": "Évolution"
        }

        widths = {
            "point": 250,
            "kilometer": 70,
            "passage_time": 120,
            "race_time": 120,
            "speed": 100,
            "effort_speed": 100,  # Ajout de la largeur pour effort_speed
            "elevation_gain": 80,
            "elevation_loss": 80,
            "rank": 80,
            "rank_evolution": 100
        }

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        # Remplir le tableau
        for checkpoint in checkpoint_data:
            elevation_gain = f"{checkpoint['elevation_gain']}m" if checkpoint['elevation_gain'] else "-"
            elevation_loss = f"{checkpoint['elevation_loss']}m" if checkpoint['elevation_loss'] else "-"

            rank_evolution = checkpoint['rank_evolution']
            if rank_evolution:
                if rank_evolution > 0:
                    evolution_text = f"+{rank_evolution}"
                else:
                    evolution_text = str(rank_evolution)
            else:
                evolution_text = "-"

            self.tree.insert('', 'end', values=(
                checkpoint['point'],
                f"{checkpoint['kilometer']:.1f}",
                checkpoint['passage_time'],
                checkpoint['race_time'],
                checkpoint['speed'],
                checkpoint['effort_speed'],
                elevation_gain,
                elevation_loss,
                checkpoint['rank'] if checkpoint['rank'] else "-",
                evolution_text
            ))

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)


class RaceTrackerApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Suivi Grand Raid")
        # Maximiser la fenêtre
        self.root.state('zoomed')

        style = ttk.Style()
        style.theme_use('default')
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="white",
            rowheight=25,
            fieldbackground="#2b2b2b"
        )
        style.configure(
            "Treeview.Heading",
            background="#2b2b2b",
            foreground="white",
            relief="flat"
        )
        style.map("Treeview", background=[('selected', '#22559b')])

        self.scraper = RaceDataScraper()
        self.checkpoint_windows = {}
        self.initial_data = []  # Pour stocker les données initiales
        self.current_filters = {
            'race': "Toutes les courses",
            'state': "Tous les états",
            'category': "Toutes les catégories"
        }
        self.create_widgets()
        self.load_cached_data()

    def create_export_button(self):
        """Créer le bouton d'export avec une image"""
        export_frame = ctk.CTkFrame(self.input_frame)  # Maintenant self.input_frame existe
        export_frame.pack(side=tk.LEFT, padx=20)

        try:
            image = Image.open("dl.png")
            image = image.resize((20, 20))
            photo = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter HTML",
                image=photo,
                compound="left",
                command=self.export_to_html
            )
        except Exception as e:
            print(f"Erreur lors du chargement de l'image: {e}")
            # Fallback si l'image n'est pas trouvée
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter HTML",
                command=self.export_to_html
            )

        self.export_button.pack(side=tk.LEFT)

    def export_to_html(self):
        """Exporter les données en HTML avec une meilleure organisation des fichiers"""
        try:
            # Créer un dossier pour les exports s'il n'existe pas
            export_dir = "exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            # Timestamp pour le nom des fichiers
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Créer le dossier des coureurs pour cette export
            runners_dir = os.path.join(export_dir, f"coureurs_{timestamp}")
            os.makedirs(runners_dir)

            # Exporter le tableau principal dans le dossier principal
            main_table_html = self.create_main_table_html(timestamp)  # Passer le timestamp à la fonction
            main_file = os.path.join(export_dir, f"tableau_principal_{timestamp}.html")
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(main_table_html)

            # Exporter les détails des coureurs dans le sous-dossier
            for bib in self.scraper.all_data:
                runner_html = self.create_runner_table_html(bib, timestamp)  # Passer le timestamp à la fonction
                if runner_html:
                    runner_file = os.path.join(runners_dir, f"coureur_{bib}.html")
                    with open(runner_file, "w", encoding="utf-8") as f:
                        f.write(runner_html)

            # Ouvrir le tableau principal dans le navigateur
            webbrowser.open(f"file://{os.path.abspath(main_file)}")
            messagebox.showinfo(
                "Export réussi",
                f"Les fichiers ont été exportés :\n"
                f"- Tableau principal : {os.path.basename(main_file)}\n"
                f"- Détails des coureurs : dossier {os.path.basename(runners_dir)}"
            )

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {str(e)}")

    def create_main_table_html(self, timestamp):
        """Créer le HTML pour le tableau principal avec tri et liens vers les détails"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Tableau des coureurs</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
            <script type="text/javascript" src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
            <script type="text/javascript" src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
            <style>
                .runner-link {
                    text-decoration: none;
                    color: inherit;
                }
                .runner-link:hover {
                    text-decoration: underline;
                    color: #0056b3;
                }
            </style>
        </head>
        <body>
            <div class="container-fluid mt-3">
                <div class="row mb-3">
                    <div class="col">
                        <h3>Tableau des coureurs</h3>
                        <p class="text-muted">Cliquez sur un dossard pour voir les détails du coureur</p>
                    </div>
                </div>
                <table id="mainTable" class="table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th>Course</th>
                            <th>Dossard</th>
                            <th>Nom</th>
                            <th>Catégorie</th>
                            <th>Class. Général</th>
                            <th>Class. Sexe</th>
                            <th>Class. Catégorie</th>
                            <th>Vitesse moy.</th>
                            <th>État</th>
                            <th>Dernier Point</th>
                            <th>Temps</th>
                            <th>D+ Total</th>
                            <th>D- Total</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        # Ajouter les données avec liens vers les détails des coureurs
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            html += "<tr>"
            for i, value in enumerate(values):
                if i == 1:  # Colonne du dossard
                    html += f'<td><a href="coureurs_{timestamp}/coureur_{value}.html" class="runner-link" target="_blank">{value}</a></td>'
                else:
                    html += f"<td>{value}</td>"
            html += "</tr>"

        html += """
                    </tbody>
                </table>
            </div>
            <script>
                $(document).ready(function() {
                    $('#mainTable').DataTable({
                        "pageLength": 50,
                        "language": {
                            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                        },
                        "order": [[1, "asc"]]  // Tri par défaut sur le dossard
                    });
                });
            </script>
        </body>
        </html>
        """
        return html

    def create_runner_table_html(self, bib, timestamp):
        """Créer le HTML pour le tableau détaillé d'un coureur avec lien retour"""
        if bib not in self.scraper.all_data:
            return None

        # Récupérer les données du coureur
        runner_data = self.scraper.all_data[bib]

        # Debug pour vérifier la structure des données
        print(f"\nDonnées du coureur {bib}:")
        print(f"Clés disponibles: {runner_data.keys()}")
        if 'checkpoints' in runner_data:
            print(f"Nombre de checkpoints: {len(runner_data['checkpoints'])}")
            if len(runner_data['checkpoints']) > 0:
                print(f"Structure d'un checkpoint: {runner_data['checkpoints'][0].keys()}")

        html_start = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Détails coureur {bib}</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <style>
                .positive-evolution {{ color: green; }}
                .negative-evolution {{ color: red; }}
                .neutral-evolution {{ color: gray; }}
            </style>
        </head>
        <body>
            <div class="container-fluid mt-3">
                <div class="row mb-3">
                    <div class="col">
                        <a href="../tableau_principal_{timestamp}.html" class="btn btn-secondary mb-3">
                            ← Retour au tableau principal
                        </a>
                        <h3>Détails du coureur {bib}</h3>
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col">
                        <h4>Informations coureur</h4>
                        <table class="table table-bordered">
                            <tr>
                                <th class="bg-light" style="width: 25%">Course</th>
                                <td style="width: 25%">{runner_data['infos']['race_name']}</td>
                                <th class="bg-light" style="width: 25%">Dossard</th>
                                <td style="width: 25%">{bib}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">Nom</th>
                                <td>{runner_data['infos']['name']}</td>
                                <th class="bg-light">Catégorie</th>
                                <td>{runner_data['infos']['category']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">État</th>
                                <td>{runner_data['infos']['state']}</td>
                                <th class="bg-light">Temps</th>
                                <td>{runner_data['infos']['finish_time']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">Class. Général</th>
                                <td>{runner_data['infos']['overall_rank']}</td>
                                <th class="bg-light">Class. Sexe</th>
                                <td>{runner_data['infos']['gender_rank']}</td>
                            </tr>
                            <tr>
                                <th class="bg-light">D+ Total</th>
                                <td>{runner_data['infos']['total_elevation_gain']}m</td>
                                <th class="bg-light">D- Total</th>
                                <td>{runner_data['infos']['total_elevation_loss']}m</td>
                            </tr>
                        </table>
                    </div>
                </div>
        """

        # Ajout de la section des points de passage uniquement s'ils existent
        html_checkpoints = """
                <div class="row">
                    <div class="col">
                        <h4>Points de passage</h4>
                        <table class="table table-striped table-bordered">
                            <thead class="table-light">
                                <tr>
                                    <th>Point</th>
                                    <th>KM</th>
                                    <th>Heure passage</th>
                                    <th>Temps course</th>
                                    <th>Vitesse</th>
                                    <th>Vitesse effort</th>
                                    <th>D+</th>
                                    <th>D-</th>
                                    <th>Class.</th>
                                    <th>Évolution</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        # Vérifier si nous avons des points de passage
        if 'checkpoints' in runner_data and runner_data['checkpoints']:
            for cp in runner_data['checkpoints']:
                # Formatage de l'évolution avec gestion des cas nuls
                evolution = cp.get('rank_evolution')
                if evolution is not None:
                    if evolution > 0:
                        evolution_text = f'<span class="positive-evolution">+{evolution}</span>'
                    elif evolution < 0:
                        evolution_text = f'<span class="negative-evolution">{evolution}</span>'
                    else:
                        evolution_text = f'<span class="neutral-evolution">{evolution}</span>'
                else:
                    evolution_text = '-'

                # Formatage des autres valeurs avec gestion des cas nuls
                kilometer = f"{cp.get('kilometer', 0):.1f}" if cp.get('kilometer') is not None else "-"
                elevation_gain = f"{cp.get('elevation_gain', 0)}m" if cp.get('elevation_gain') is not None else "-"
                elevation_loss = f"{cp.get('elevation_loss', 0)}m" if cp.get('elevation_loss') is not None else "-"

                html_checkpoints += f"""
                    <tr>
                        <td>{cp.get('point', '-')}</td>
                        <td>{kilometer}</td>
                        <td>{cp.get('passage_time', '-')}</td>
                        <td>{cp.get('race_time', '-')}</td>
                        <td>{cp.get('speed', '-')}</td>
                        <td>{cp.get('effort_speed', '-')}</td>
                        <td>{elevation_gain}</td>
                        <td>{elevation_loss}</td>
                        <td>{cp.get('rank', '-')}</td>
                        <td>{evolution_text}</td>
                    </tr>
                """

            html_checkpoints += """
                            </tbody>
                        </table>
                    </div>
                </div>
            """
        else:
            # Message si pas de points de passage
            html_checkpoints = """
                <div class="row">
                    <div class="col">
                        <div class="alert alert-info" role="alert">
                            Aucun point de passage disponible pour ce coureur.
                        </div>
                    </div>
                </div>
            """

        html_end = """
            </div>
        </body>
        </html>
        """

        full_html = html_start + html_checkpoints + html_end
        print(f"HTML généré pour le coureur {bib}")
        return full_html



    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Frame de saisie
        self.input_frame = ctk.CTkFrame(self.main_frame)
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        ctk.CTkLabel(self.input_frame, text="Numéros de dossard (séparés par des virgules):").pack(side=tk.LEFT, padx=5)
        self.bib_entry = ctk.CTkEntry(self.input_frame, width=400)
        self.bib_entry.pack(side=tk.LEFT, padx=5)

        self.scan_button = ctk.CTkButton(self.input_frame, text="Scanner", command=self.start_scanning)
        self.scan_button.pack(side=tk.LEFT, padx=5)

        # Frame de progression
        progress_frame = ctk.CTkFrame(self.main_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.progress_label = ctk.CTkLabel(progress_frame, text="")
        self.progress_label.pack(side=tk.LEFT, padx=5)

        # Configuration du tableau principal
        columns = (
            "race_name", "bib", "name", "category", "overall_rank", "gender_rank",
            "category_rank", "average_speed", "state", "last_checkpoint",
            "finish_time", "total_elevation_gain", "total_elevation_loss"
        )

        tree_frame = ttk.Frame(self.main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings"
        )

        # Configuration des colonnes
        headers = {
            "race_name": "Course",  # Ajout de l'en-tête pour la course
            "bib": "Dossard",
            "name": "Nom",
            "category": "Catégorie",
            "overall_rank": "Class. Général",
            "gender_rank": "Class. Sexe",
            "category_rank": "Class. Catégorie",
            "average_speed": "Vitesse moy.",
            "state": "État",
            "last_checkpoint": "Dernier Point",
            "finish_time": "Temps",
            "total_elevation_gain": "D+ Total",
            "total_elevation_loss": "D- Total"
        }

        widths = {
            "race_name": 150,  # Ajout de la largeur pour la colonne course
            "bib": 80,
            "name": 200,
            "category": 100,
            "overall_rank": 100,
            "gender_rank": 100,
            "category_rank": 120,
            "average_speed": 100,
            "state": 100,
            "last_checkpoint": 200,
            "finish_time": 100,
            "total_elevation_gain": 100,
            "total_elevation_loss": 100
        }

        for col in columns:
            self.tree.heading(
                col,
                text=headers[col],
                command=lambda c=col: self.treeview_sort_column(c, False)
            )
            self.tree.column(col, width=widths[col], anchor="center")

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind('<Double-1>', self.show_checkpoint_details)

        # Frame pour les filtres
        filter_frame = ctk.CTkFrame(self.main_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ctk.CTkLabel(filter_frame, text="Filtres:").pack(side=tk.LEFT, padx=5)

        # Créer les widgets de filtre avec les nouveaux callbacks
        self.race_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Toutes les courses"],
            command=lambda x: self.on_filter_change('race', x)
        )
        self.race_filter.pack(side=tk.LEFT, padx=5)
        self.race_filter.set("Toutes les courses")

        self.state_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Tous les états"],
            command=lambda x: self.on_filter_change('state', x)
        )
        self.state_filter.pack(side=tk.LEFT, padx=5)
        self.state_filter.set("Tous les états")

        self.category_filter = ctk.CTkComboBox(
            filter_frame,
            values=["Toutes les catégories"],
            command=lambda x: self.on_filter_change('category', x)
        )
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.set("Toutes les catégories")

        # Ajouter un bouton de réinitialisation
        self.reset_filters_button = ctk.CTkButton(
            filter_frame,
            text="Réinitialiser les filtres",
            command=self.reset_filters
        )
        self.reset_filters_button.pack(side=tk.LEFT, padx=20)

        # Ajouter le bouton TOP Analyses dans self.input_frame
        self.analysis_button = ctk.CTkButton(
            self.input_frame,  # Utiliser self.input_frame ici
            text="TOP Analyses",
            command=self.show_top_analysis
        )
        self.analysis_button.pack(side=tk.LEFT, padx=5)

        # Ajouter le bouton d'export
        self.create_export_button()

    def load_initial_data(self):
        """Charger et stocker les données initiales"""
        self.initial_data.clear()
        for item in self.tree.get_children():
            self.initial_data.append(self.tree.item(item))

    def on_filter_change(self, filter_type, value):
        """Gestion du changement de filtre avec type de filtre"""
        print(f"Changement du filtre {filter_type}: {value}")
        self.current_filters[filter_type] = value
        self.apply_filters()

    def reset_filters(self):
        """Réinitialiser tous les filtres et restaurer les données initiales"""
        # Réinitialiser les valeurs des filtres
        self.race_filter.set("Toutes les courses")
        self.state_filter.set("Tous les états")
        self.category_filter.set("Toutes les catégories")

        self.current_filters = {
            'race': "Toutes les courses",
            'state': "Tous les états",
            'category': "Toutes les catégories"
        }

        # Effacer le tableau actuel
        self.tree.delete(*self.tree.get_children())

        # Restaurer les données initiales
        for item_data in self.initial_data:
            self.tree.insert('', 'end', values=item_data['values'], tags=item_data.get('tags', ()))

        print("Filtres réinitialisés - Données restaurées à l'état initial")
        print(f"Nombre total de coureurs: {len(self.initial_data)}")

    def load_cached_data(self):
        """Charger les données en cache et initialiser les données de référence"""
        if self.scraper.all_data:
            cached_bibs = list(self.scraper.all_data.keys())
            print(f"Chargement automatique de {len(cached_bibs)} dossards")
            for bib in cached_bibs:
                data = self.scraper.all_data[bib]
                self.add_runner_to_tree(data)

            # Stocker les données initiales après le chargement
            self.load_initial_data()

            self.update_filters()
            self.progress_label.configure(text=f"{len(cached_bibs)} dossards chargés depuis le cache")

    def show_top_analysis(self):
        # Récupérer tous les dossards actuellement affichés dans le tableau
        bibs = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values:
                bibs.append(values[1])  # L'index 1 correspond à la colonne du dossard

        if not bibs:
            messagebox.showwarning(
                "Attention",
                "Aucun coureur n'est actuellement affiché dans le tableau!"
            )
            return

        # Créer la fenêtre d'analyse
        TopAnalysisWindow(self.root, self.scraper, bibs)

    def scanning_complete(self, scanned, cached):
        """Finalise le processus de scan"""
        self.scan_button.configure(state="normal")
        if scanned + cached > 0:
            self.progress_label.configure(
                text=f"Scan terminé ! ({cached} depuis le cache, {scanned} nouveaux scans)"
            )
        else:
            self.progress_label.configure(text="Scan terminé !")

    def show_checkpoint_details(self, event):
        """Affiche la fenêtre des détails pour un coureur"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item)['values']
        if not values:
            return

        bib_number = str(values[1])  # Le dossard est maintenant la deuxième colonne (index 1)

        if bib_number in self.scraper.all_data:
            # Créer une nouvelle fenêtre ou mettre à jour l'existante
            if bib_number in self.checkpoint_windows:
                self.checkpoint_windows[bib_number].window.destroy()

            # Récupérer les données du coureur
            runner_data = self.scraper.all_data[bib_number]['infos']

            # Créer la nouvelle fenêtre
            self.checkpoint_windows[bib_number] = CheckpointWindow(
                self.root,
                bib_number,
                runner_data,
                self.scraper.all_data[bib_number]['checkpoints']
            )
        else:
            messagebox.showwarning(
                "Données non disponibles",
                f"Pas de données de points de passage pour le dossard {bib_number}"
            )

    def treeview_sort_column(self, col, reverse):
        """Trie le tableau selon une colonne avec gestion correcte des nombres"""
        try:
            data = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

            def convert_to_number(value):
                """Convertit une valeur en nombre en gérant les cas spéciaux"""
                if not value or value.strip() == '-':
                    return float('inf')  # Mettre les valeurs vides à la fin
                try:
                    # Nettoyer la valeur et convertir en nombre
                    clean_value = ''.join(c for c in value if c.isdigit() or c == '.')
                    return float(clean_value) if '.' in clean_value else int(clean_value)
                except:
                    return value

            # Détermine si la colonne doit être triée numériquement
            numeric_columns = {
                "overall_rank", "gender_rank", "category_rank",  # Classements
                "bib",  # Dossards
                "total_elevation_gain", "total_elevation_loss"  # Dénivelés
            }

            # Tri avec gestion spéciale pour les colonnes numériques
            if col in numeric_columns:
                data.sort(
                    key=lambda x: convert_to_number(x[0]),
                    reverse=reverse
                )
            else:
                # Tri normal pour les autres colonnes
                data.sort(
                    key=lambda x: x[0].lower() if isinstance(x[0], str) else x[0],
                    reverse=reverse
                )

            # Réorganiser les items
            for idx, (val, item) in enumerate(data):
                self.tree.move(item, '', idx)

            # Inverser le sens pour le prochain clic
            self.tree.heading(
                col,
                text=self.tree.heading(col)['text'],
                command=lambda: self.treeview_sort_column(col, not reverse)
            )

        except Exception as e:
            print(f"Erreur lors du tri de la colonne {col}: {e}")
            traceback.print_exc()


    def add_runner_to_tree(self, data):
        """Ajoute un coureur au tableau principal avec toutes les nouvelles données"""
        if data and 'infos' in data:
            info = data['infos']
            self.tree.insert('', 'end', values=(
                info['race_name'],  # Ajout du nom de la course
                info['bib_number'],
                info['name'],
                info['category'],
                info['overall_rank'],
                info['gender_rank'],
                info['category_rank'],
                info['average_speed'],
                info['state'],
                info['last_checkpoint'],
                info['finish_time'],
                f"{info['total_elevation_gain']}m",
                f"{info['total_elevation_loss']}m"
            ))

    def update_filters(self):
        """Mise à jour des listes de filtres en fonction des données actuelles"""
        categories = set()
        states = set()
        races = set()
        races.add("Toutes les courses")
        states.add("Tous les états")
        categories.add("Toutes les catégories")

        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values:
                races.add(values[0])  # Course (index 0)
                categories.add(values[3])  # Catégorie (index 3)
                states.add(values[8])  # État (index 8)

        # Mettre à jour les valeurs des ComboBox
        self.race_filter.configure(values=sorted(list(races)))
        self.state_filter.configure(values=sorted(list(states)))
        self.category_filter.configure(values=sorted(list(categories)))



    def apply_filters(self):
        """Application des filtres avec gestion améliorée"""
        # Sauvegarder toutes les lignes originales
        all_items = [(self.tree.item(item), item) for item in self.tree.get_children()]

        # Effacer l'affichage actuel
        self.tree.delete(*self.tree.get_children())

        filtered_count = 0

        for item_data, item_id in all_items:
            values = item_data['values']
            if not values:
                continue

            show_item = True

            # Vérifier chaque filtre
            if self.current_filters['race'] != "Toutes les courses" and values[0] != self.current_filters['race']:
                show_item = False
            if self.current_filters['category'] != "Toutes les catégories" and values[3] != self.current_filters[
                'category']:
                show_item = False
            if self.current_filters['state'] != "Tous les états" and values[8] != self.current_filters['state']:
                show_item = False

            if show_item:
                self.tree.insert('', 'end', values=values, tags=item_data.get('tags', ()))
                filtered_count += 1

        # Afficher un résumé des filtres appliqués
        filter_summary = []
        if self.current_filters['race'] != "Toutes les courses":
            filter_summary.append(f"Course: {self.current_filters['race']}")
        if self.current_filters['category'] != "Toutes les catégories":
            filter_summary.append(f"Catégorie: {self.current_filters['category']}")
        if self.current_filters['state'] != "Tous les états":
            filter_summary.append(f"État: {self.current_filters['state']}")

        print(f"Filtres actifs: {' | '.join(filter_summary) if filter_summary else 'Aucun'}")
        print(f"Nombre de coureurs affichés: {filtered_count}")


    def scan_bibs(self, bib_numbers):
        total = len(bib_numbers)
        scanned = 0
        cached = 0

        for i, bib in enumerate(bib_numbers, 1):
            bib_str = str(bib)
            if bib_str in self.scraper.all_data:
                self.progress_label.configure(
                    text=f"Récupération du cache pour le dossard {bib} ({i}/{total})..."
                )
                data = self.scraper.all_data[bib_str]
                cached += 1
            else:
                self.progress_label.configure(
                    text=f"Scan du dossard {bib} ({i}/{total})..."
                )
                data = self.scraper.get_runner_data(bib)
                scanned += 1

            if data:
                self.root.after(0, self.add_runner_to_tree, data)
            # time.sleep(1)

        self.root.after(0, lambda: self.scanning_complete(scanned, cached))
        self.root.after(0, self.update_filters)

    def start_scanning(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        bib_text = self.bib_entry.get().strip()
        if not bib_text:
            messagebox.showwarning("Attention", "Veuillez entrer des numéros de dossard!")
            return

        try:
            bib_numbers = [int(x.strip()) for x in bib_text.split(',')]
        except ValueError:
            messagebox.showerror("Erreur", "Format de numéro de dossard invalide!")
            return

        self.scan_button.configure(state="disabled")
        thread = threading.Thread(target=self.scan_bibs, args=(bib_numbers,))
        thread.daemon = True
        thread.start()

    def run(self):
        self.root.mainloop()

    def __del__(self):
        if hasattr(self, 'scraper'):
            self.scraper.close_driver()


class TopAnalysisWindow:
    def __init__(self, parent, scraper, bibs):
        self.window = ctk.CTkToplevel(parent)
        self.window.title("TOP Analyses")
        self.window.geometry("1400x800")
        self.scraper = scraper
        self.bibs = bibs
        self.sections_info = {}  # Initialisation de sections_info ici

        # Frame principal avec défilement
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Frame pour les filtres en haut²
        self.filter_frame = ctk.CTkFrame(self.main_frame)
        self.filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # Sélecteur de course
        ctk.CTkLabel(self.filter_frame, text="Course:").pack(side=tk.LEFT, padx=5)
        self.race_values = self.get_unique_races()
        self.race_selector = ctk.CTkComboBox(
            self.filter_frame,
            values=self.race_values,
            command=self.on_race_selected
        )
        self.race_selector.pack(side=tk.LEFT, padx=5)
        self.race_selector.set("Toutes les courses")

        # Sélecteur de section (visible uniquement pour l'onglet sections)
        self.section_frame = ctk.CTkFrame(self.filter_frame)
        self.section_selector = None

        # Après la création du section_selector
        self.create_export_button()

        # Créer les onglets
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill=tk.BOTH, expand=True, pady=10)

        # Ajouter les onglets
        self.tab_progress = self.tabview.add("Progression")
        self.tab_elevation = self.tabview.add("Dénivelés")
        self.tab_speed = self.tabview.add("Vitesses")
        self.tab_sections = self.tabview.add("Sections")

        # Créer les sous-onglets pour chaque catégorie principale
        self.create_progression_subtabs()
        self.create_elevation_subtabs()
        self.create_speed_subtabs()
        self.create_sections_subtabs()

        # Initialiser l'affichage
        self.update_displays()

    def get_unique_races(self):
        races = set()
        races.add("Toutes les courses")
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                race_name = self.scraper.all_data[str(bib)]['infos']['race_name']
                races.add(race_name)
        return sorted(list(races))

    def create_progression_subtabs(self):
        self.progress_tabs = ctk.CTkTabview(self.tab_progress)
        self.progress_tabs.pack(fill=tk.BOTH, expand=True)

        self.progress_global = self.progress_tabs.add("Progression globale")
        self.progress_sections = self.progress_tabs.add("Entre points")

        # Ajouter ScrollArea pour chaque sous-onglet
        self.progress_global_scroll = ctk.CTkScrollableFrame(self.progress_global)
        self.progress_global_scroll.pack(fill=tk.BOTH, expand=True)

        self.progress_sections_scroll = ctk.CTkScrollableFrame(self.progress_sections)
        self.progress_sections_scroll.pack(fill=tk.BOTH, expand=True)

    def create_elevation_subtabs(self):
        self.elevation_tabs = ctk.CTkTabview(self.tab_elevation)
        self.elevation_tabs.pack(fill=tk.BOTH, expand=True)

        self.elevation_climbers = self.elevation_tabs.add("Grimpeurs")
        self.elevation_descenders = self.elevation_tabs.add("Descendeurs")

        self.climbers_scroll = ctk.CTkScrollableFrame(self.elevation_climbers)
        self.climbers_scroll.pack(fill=tk.BOTH, expand=True)

        self.descenders_scroll = ctk.CTkScrollableFrame(self.elevation_descenders)
        self.descenders_scroll.pack(fill=tk.BOTH, expand=True)

    def create_speed_subtabs(self):
        self.speed_tabs = ctk.CTkTabview(self.tab_speed)
        self.speed_tabs.pack(fill=tk.BOTH, expand=True)

        self.speed_avg = self.speed_tabs.add("Vitesse moyenne")
        self.speed_effort = self.speed_tabs.add("Vitesse effort")
        self.speed_sections = self.speed_tabs.add("Entre points")

        self.speed_avg_scroll = ctk.CTkScrollableFrame(self.speed_avg)
        self.speed_avg_scroll.pack(fill=tk.BOTH, expand=True)

        self.speed_effort_scroll = ctk.CTkScrollableFrame(self.speed_effort)
        self.speed_effort_scroll.pack(fill=tk.BOTH, expand=True)

        self.speed_sections_scroll = ctk.CTkScrollableFrame(self.speed_sections)
        self.speed_sections_scroll.pack(fill=tk.BOTH, expand=True)

    def create_sections_subtabs(self):
        self.sections_frame = ctk.CTkFrame(self.tab_sections)
        self.sections_frame.pack(fill=tk.BOTH, expand=True)

        # Ajouter le sélecteur de sections
        self.section_frame.pack(side=tk.LEFT, padx=20)
        ctk.CTkLabel(self.section_frame, text="Section:").pack(side=tk.LEFT, padx=5)
        self.section_selector = ctk.CTkComboBox(
            self.section_frame,
            values=[],
            command=self.on_section_selected
        )
        self.section_selector.pack(side=tk.LEFT, padx=5)

        # Frame pour les résultats de section avec scroll
        self.section_results_scroll = ctk.CTkScrollableFrame(self.sections_frame)
        self.section_results_scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_race_selected(self, selection):
        # Mettre à jour les sections disponibles
        self.update_section_selector(selection)
        # Mettre à jour tous les affichages
        self.update_displays()

    def on_section_selected(self, selection):
        # Mettre à jour l'affichage des performances de la section
        self.update_section_display()

    def update_section_selector(self, race):
        """Mettre à jour la liste des sections avec les données associées"""
        self.sections_info = {}  # Réinitialiser les infos de section
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if race == "Toutes les courses" or data['infos']['race_name'] == race:
                    checkpoints = data['checkpoints']
                    for i in range(len(checkpoints) - 1):
                        section_name = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                        if section_name not in self.sections_info:
                            self.sections_info[section_name] = {
                                'name': section_name,
                                'distance': checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer'],
                                'elevation_gain': checkpoints[i + 1]['elevation_gain'],
                                'elevation_loss': checkpoints[i + 1]['elevation_loss']
                            }

        # Mettre à jour le ComboBox avec les noms des sections
        section_names = sorted(list(self.sections_info.keys()))
        self.section_selector.configure(values=section_names)
        if section_names:
            self.section_selector.set(section_names[0])

    def update_displays(self):
        """Mettre à jour tous les affichages en fonction de la course sélectionnée"""
        self.clear_all_displays()
        selected_race = self.race_selector.get()

        # Mettre à jour les progressions
        self.update_progression_displays(selected_race)

        # Mettre à jour les dénivelés
        self.update_elevation_displays(selected_race)

        # Mettre à jour les vitesses
        self.update_speed_displays(selected_race)

        # Mettre à jour l'affichage des sections
        self.update_section_display()

    def clear_all_displays(self):
        """Effacer tous les affichages existants"""
        for widget in self.progress_global_scroll.winfo_children():
            widget.destroy()
        for widget in self.progress_sections_scroll.winfo_children():
            widget.destroy()
        for widget in self.climbers_scroll.winfo_children():
            widget.destroy()
        for widget in self.descenders_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_avg_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_effort_scroll.winfo_children():
            widget.destroy()
        for widget in self.speed_sections_scroll.winfo_children():
            widget.destroy()
        for widget in self.section_results_scroll.winfo_children():
            widget.destroy()

    def create_table(self, parent, columns, headers, data, height=10, tooltips=None):
        """Créer un tableau personnalisé avec style uniforme et infobulles"""
        style = ttk.Style()
        style.configure(
            "Custom.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            rowheight=30
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#2b2b2b",
            foreground="white"
        )

        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            height=height,
            style="Custom.Treeview"
        )

        # Création des infobulles
        tooltip = None
        if tooltips:
            from tkinter import messagebox
            def show_tooltip(event):
                column = tree.identify_column(event.x)
                col_id = int(column.replace('#', '')) - 1
                if col_id < len(columns) and columns[col_id] in tooltips:
                    messagebox.showinfo("Information", tooltips[columns[col_id]])

            tree.bind('<Button-3>', show_tooltip)  # Clic droit pour afficher l'infobulle

        for col in columns:
            header_text = headers[col]
            if tooltips and col in tooltips:
                header_text += " (❓)"  # Ajouter un indicateur visuel
            tree.heading(col, text=header_text)
            tree.column(col, width=headers.get(f"{col}_width", 100), anchor="center")

        # Ajouter les données
        for row in data:
            tree.insert("", "end", values=row)

        return tree

    def create_section_info_card(self, parent, section_info):
        """Créer une carte d'information pour une section avec infobulles"""
        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.X, padx=5, pady=5)

        title = ctk.CTkLabel(
            frame,
            text=section_info['name'],
            font=("Arial", 16, "bold")
        )
        title.pack(pady=5)

        # Création d'un frame pour les informations avec infobulles
        info_frame = ctk.CTkFrame(frame)
        info_frame.pack(pady=5)

        # Distance
        distance_frame = ctk.CTkFrame(info_frame)
        distance_frame.pack(side=tk.LEFT, padx=10)
        distance_label = ctk.CTkLabel(
            distance_frame,
            text=f"Distance: {section_info['distance']:.1f}km"
        )
        distance_label.pack(side=tk.LEFT)

        def show_distance_info():
            messagebox.showinfo("Information",
                                "Distance horizontale entre les deux points de la section.")

        distance_info = ctk.CTkButton(
            distance_frame,
            text="❓",
            width=20,
            command=show_distance_info
        )
        distance_info.pack(side=tk.LEFT, padx=2)

        # Dénivelé positif
        dplus_frame = ctk.CTkFrame(info_frame)
        dplus_frame.pack(side=tk.LEFT, padx=10)
        dplus_label = ctk.CTkLabel(
            dplus_frame,
            text=f"D+: {section_info['elevation_gain']}m"
        )
        dplus_label.pack(side=tk.LEFT)

        def show_dplus_info():
            messagebox.showinfo("Information",
                                "Dénivelé positif accumulé sur la section.\n"
                                "Représente la somme des montées uniquement.")

        dplus_info = ctk.CTkButton(
            dplus_frame,
            text="❓",
            width=20,
            command=show_dplus_info
        )
        dplus_info.pack(side=tk.LEFT, padx=2)

        # Dénivelé négatif
        dminus_frame = ctk.CTkFrame(info_frame)
        dminus_frame.pack(side=tk.LEFT, padx=10)
        dminus_label = ctk.CTkLabel(
            dminus_frame,
            text=f"D-: {section_info['elevation_loss']}m"
        )
        dminus_label.pack(side=tk.LEFT)

        def show_dminus_info():
            messagebox.showinfo("Information",
                                "Dénivelé négatif accumulé sur la section.\n"
                                "Représente la somme des descentes uniquement.")

        dminus_info = ctk.CTkButton(
            dminus_frame,
            text="❓",
            width=20,
            command=show_dminus_info
        )
        dminus_info.pack(side=tk.LEFT, padx=2)

        return frame


    def update_progression_displays(self, selected_race):
        """Mettre à jour les affichages de progression"""
        # Progression globale
        global_progressions = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']
                    if len(checkpoints) >= 2:
                        first_rank = None
                        last_rank = None

                        for cp in checkpoints:
                            if cp['rank'] is not None:
                                try:
                                    rank = int(cp['rank'])
                                    if first_rank is None:
                                        first_rank = rank
                                    last_rank = rank
                                except ValueError:
                                    continue

                        if first_rank is not None and last_rank is not None:
                            progression = first_rank - last_rank
                            global_progressions.append({
                                'progression': progression,
                                'bib': bib,
                                'name': data['infos']['name'],
                                'race': data['infos']['race_name'],
                                'start_pos': first_rank,
                                'end_pos': last_rank
                            })

        # Trier et afficher les meilleures progressions
        global_progressions.sort(key=lambda x: x['progression'], reverse=True)

        columns = ["rank", "bib", "name", "race", "start_pos", "end_pos", "progression"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "start_pos": "Pos. départ",
            "start_pos_width": 100,
            "end_pos": "Pos. finale",
            "end_pos_width": 100,
            "progression": "Progression",
            "progression_width": 100
        }

        data = [
            (
                i + 1,
                prog['bib'],
                prog['name'],
                prog['race'],
                prog['start_pos'],
                prog['end_pos'],
                f"+{prog['progression']}" if prog['progression'] > 0 else str(prog['progression'])
            )
            for i, prog in enumerate(global_progressions[:20])
        ]

        # Ajouter les tooltips pour la progression globale
        tooltips = {
            "progression": "Places gagnées entre le premier et le dernier point de passage.",
            "start_pos": "Position au premier point de chronométrage.",
            "end_pos": "Position finale du coureur."
        }

        if data:
            ctk.CTkLabel(
                self.progress_global_scroll,
                text="Top 20 des meilleures progressions (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            tree = self.create_table(self.progress_global_scroll, columns, headers, data, tooltips=tooltips)
            tree.pack(fill=tk.X, padx=5, pady=5)

        # Ajouter les tooltips pour la progression entre points
        section_tooltips = {
            "section": "Points de passage entre lesquels la progression est calculée",
            "progression": "Nombre de places gagnées sur cette section spécifique",
            "ranks": "Positions au début et à la fin de la section"
        }


        # Progression entre points
        section_progressions = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i]['rank'] and checkpoints[i + 1]['rank']:
                            try:
                                rank1 = int(checkpoints[i]['rank'])
                                rank2 = int(checkpoints[i + 1]['rank'])
                                progression = rank1 - rank2
                                if progression > 0:
                                    section_progressions.append({
                                        'progression': progression,
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'from_point': checkpoints[i]['point'],
                                        'to_point': checkpoints[i + 1]['point'],
                                        'start_rank': rank1,
                                        'end_rank': rank2
                                    })
                            except ValueError:
                                continue

        section_progressions.sort(key=lambda x: x['progression'], reverse=True)

        if section_progressions:
            ctk.CTkLabel(
                self.progress_sections_scroll,
                text="Top 20 des meilleures progressions entre points",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            columns = ["rank", "bib", "name", "race", "section", "progression", "ranks"]
            headers = {
                "rank": "Position",
                "rank_width": 80,
                "bib": "Dossard",
                "bib_width": 80,
                "name": "Nom",
                "name_width": 200,
                "race": "Course",
                "race_width": 150,
                "section": "Section",
                "section_width": 300,
                "progression": "Progression",
                "progression_width": 100,
                "ranks": "Classements",
                "ranks_width": 150
            }

            data = [
                (
                    i + 1,
                    prog['bib'],
                    prog['name'],
                    prog['race'],
                    f"{prog['from_point']} → {prog['to_point']}",
                    f"+{prog['progression']}",
                    f"{prog['start_rank']} → {prog['end_rank']}"
                )
                for i, prog in enumerate(section_progressions[:20])
            ]

            tree = self.create_table(self.progress_sections_scroll, columns, headers, data)
            tree.pack(fill=tk.X, padx=5, pady=5)

    def update_elevation_displays(self, selected_race):
        """Mettre à jour les affichages de dénivelé avec tooltips et indicateurs de tendance"""
        # Calcul pour les grimpeurs
        climbers = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']
                    total_elevation_time = 0
                    total_elevation_gain = 0
                    total_distance = 0

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i]['elevation_gain'] > 100:  # Sections significatives
                            try:
                                time1 = datetime.strptime(checkpoints[i]['race_time'], "%H:%M:%S")
                                time2 = datetime.strptime(checkpoints[i + 1]['race_time'], "%H:%M:%S")
                                segment_time = (time2 - time1).total_seconds() / 3600
                                distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                if segment_time > 0:
                                    total_elevation_time += segment_time
                                    total_elevation_gain += checkpoints[i]['elevation_gain']
                                    total_distance += distance
                            except:
                                continue

                    if total_elevation_time > 0:
                        climbing_speed = total_elevation_gain / total_elevation_time
                        # Calculer le ratio dénivelé/distance pour évaluer la difficulté
                        elevation_ratio = total_elevation_gain / (total_distance * 1000) if total_distance > 0 else 0
                        climbers.append({
                            'speed': climbing_speed,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name'],
                            'elevation_gain': total_elevation_gain,
                            'time': total_elevation_time,
                            'distance': total_distance,
                            'elevation_ratio': elevation_ratio
                        })

        climbers.sort(key=lambda x: x['speed'], reverse=True)

        # Tooltips pour les grimpeurs
        climber_tooltips = {
            "elevation": "Dénivelé positif total cumulé sur les sections de montée significative (>100m D+)",
            "time": "Temps total passé sur les sections de montée significative",
            "speed": "Vitesse verticale moyenne en montée (mètres de dénivelé par heure)",
            "ratio": "Pourcentage moyen de pente (D+ / Distance horizontale)",
            "tendency": "Indicateur de difficulté basé sur le ratio dénivelé/distance"
        }

        if climbers:
            ctk.CTkLabel(
                self.climbers_scroll,
                text="Top 20 des meilleurs grimpeurs (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            columns = ["rank", "bib", "name", "race", "elevation", "time", "speed", "ratio", "tendency"]
            headers = {
                "rank": "Position",
                "rank_width": 80,
                "bib": "Dossard",
                "bib_width": 80,
                "name": "Nom",
                "name_width": 200,
                "race": "Course",
                "race_width": 150,
                "elevation": "D+ total",
                "elevation_width": 100,
                "time": "Temps",
                "time_width": 100,
                "speed": "Vitesse",
                "speed_width": 100,
                "ratio": "Pente moy.",
                "ratio_width": 100,
                "tendency": "Tendance",
                "tendency_width": 80
            }

            def get_climb_indicator(ratio):
                if ratio > 0.15:  # >15%
                    return "↗️↗️↗️"  # Très raide
                elif ratio > 0.10:  # >10%
                    return "↗️↗️"  # Raide
                else:
                    return "↗️"  # Modéré

            data = [
                (
                    i + 1,
                    climb['bib'],
                    climb['name'],
                    climb['race'],
                    f"{climb['elevation_gain']}m",
                    f"{climb['time']:.1f}h",
                    f"{climb['speed']:.1f} m/h",
                    f"{(climb['elevation_ratio'] * 100):.1f}%",
                    get_climb_indicator(climb['elevation_ratio'])
                )
                for i, climb in enumerate(climbers[:20])
            ]

            tree = self.create_table(self.climbers_scroll, columns, headers, data, tooltips=climber_tooltips)
            tree.pack(fill=tk.X, padx=5, pady=5)

        # Descente (avec les mêmes améliorations)
        descenders = []
        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']
                    total_descent_time = 0
                    total_elevation_loss = 0
                    total_distance = 0

                    for i in range(len(checkpoints) - 1):
                        if checkpoints[i]['elevation_loss'] > 100:
                            try:
                                time1 = datetime.strptime(checkpoints[i]['race_time'], "%H:%M:%S")
                                time2 = datetime.strptime(checkpoints[i + 1]['race_time'], "%H:%M:%S")
                                segment_time = (time2 - time1).total_seconds() / 3600
                                distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                                if segment_time > 0:
                                    total_descent_time += segment_time
                                    total_elevation_loss += abs(checkpoints[i]['elevation_loss'])
                                    total_distance += distance
                            except:
                                continue

                    if total_descent_time > 0:
                        descending_speed = total_elevation_loss / total_descent_time
                        elevation_ratio = total_elevation_loss / (total_distance * 1000) if total_distance > 0 else 0
                        descenders.append({
                            'speed': descending_speed,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name'],
                            'elevation_loss': total_elevation_loss,
                            'time': total_descent_time,
                            'distance': total_distance,
                            'elevation_ratio': elevation_ratio
                        })

        descenders.sort(key=lambda x: x['speed'], reverse=True)

        # Tooltips pour les descendeurs
        descender_tooltips = {
            "elevation": "Dénivelé négatif total cumulé sur les sections de descente significative (>100m D-)",
            "time": "Temps total passé sur les sections de descente significative",
            "speed": "Vitesse verticale moyenne en descente (mètres de dénivelé par heure)",
            "ratio": "Pourcentage moyen de pente (D- / Distance horizontale)",
            "tendency": "Indicateur de difficulté basé sur le ratio dénivelé/distance"
        }

        if descenders:
            ctk.CTkLabel(
                self.descenders_scroll,
                text="Top 20 des meilleurs descendeurs (Clic droit sur les en-têtes pour plus d'informations)",
                font=("Arial", 16, "bold")
            ).pack(pady=10)

            def get_descent_indicator(ratio):
                if ratio > 0.15:  # >15%
                    return "↘️↘️↘️"  # Très raide
                elif ratio > 0.10:  # >10%
                    return "↘️↘️"  # Raide
                else:
                    return "↘️"  # Modéré

            data = [
                (
                    i + 1,
                    desc['bib'],
                    desc['name'],
                    desc['race'],
                    f"{desc['elevation_loss']}m",
                    f"{desc['time']:.1f}h",
                    f"{desc['speed']:.1f} m/h",
                    f"{(desc['elevation_ratio'] * 100):.1f}%",
                    get_descent_indicator(desc['elevation_ratio'])
                )
                for i, desc in enumerate(descenders[:20])
            ]

            tree = self.create_table(self.descenders_scroll, columns, headers, data, tooltips=descender_tooltips)
            tree.pack(fill=tk.X, padx=5, pady=5)

    def update_speed_displays(self, selected_race):
        """Mettre à jour les affichages de vitesse"""
        speeds = []
        efforts = []
        section_speeds = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    # Calcul des vitesses moyennes
                    avg_speed = 0
                    avg_effort = 0
                    count = 0

                    for cp in checkpoints:
                        try:
                            speed = float(cp['speed'].replace('km/h', '').strip())
                            effort = float(cp['effort_speed'].replace('km/h', '').strip())
                            avg_speed += speed
                            avg_effort += effort
                            count += 1
                        except:
                            continue

                    if count > 0:
                        speeds.append({
                            'speed': avg_speed / count,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

                        efforts.append({
                            'effort': avg_effort / count,
                            'bib': bib,
                            'name': data['infos']['name'],
                            'race': data['infos']['race_name']
                        })

                    # Calcul des vitesses par section
                    for i in range(len(checkpoints) - 1):
                        try:
                            time1 = datetime.strptime(checkpoints[i]['race_time'], "%H:%M:%S")
                            time2 = datetime.strptime(checkpoints[i + 1]['race_time'], "%H:%M:%S")
                            segment_time = (time2 - time1).total_seconds() / 3600
                            distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']

                            if segment_time > 0:
                                section_speed = distance / segment_time
                                section_speeds.append({
                                    'speed': section_speed,
                                    'bib': bib,
                                    'name': data['infos']['name'],
                                    'race': data['infos']['race_name'],
                                    'from_point': checkpoints[i]['point'],
                                    'to_point': checkpoints[i + 1]['point'],
                                    'distance': distance
                                })
                        except:
                            continue

        # Afficher les vitesses moyennes
        speeds.sort(key=lambda x: x['speed'], reverse=True)
        self.display_speed_table(
            self.speed_avg_scroll,
            speeds[:20],
            "Top 20 des meilleures vitesses moyennes",
            "speed"
        )

        # Afficher les vitesses effort
        efforts.sort(key=lambda x: x['effort'], reverse=True)
        self.display_speed_table(
            self.speed_effort_scroll,
            efforts[:20],
            "Top 20 des meilleures vitesses effort",
            "effort"
        )

        # Afficher les vitesses par section
        section_speeds.sort(key=lambda x: x['speed'], reverse=True)
        self.display_section_speed_table(
            self.speed_sections_scroll,
            section_speeds[:20]
        )

    def display_speed_table(self, parent, data, title, speed_type):
        """Afficher un tableau de vitesses avec infobulles"""
        if not data:
            return

        tooltips = {
            "speed": {
                'speed': "Moyenne des vitesses instantanées sur l'ensemble du parcours (sans tenir compte du dénivelé).",
                'effort': "Moyenne des vitesses effort qui prennent en compte le dénivelé. Permet de comparer l'intensité réelle de l'effort."
            }[speed_type]
        }

        ctk.CTkLabel(
            parent,
            text=title + " (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        columns = ["rank", "bib", "name", "race", "speed"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "speed": {
                'speed': "Vitesse moyenne",
                'effort': "Vitesse effort moyenne"
            }[speed_type],
            "speed_width": 100
        }

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                f"{item[speed_type]:.1f} km/h"
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(parent, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def display_section_speed_table(self, parent, data):
        """Afficher un tableau de vitesses par section avec infobulles"""
        if not data:
            return

        tooltips = {
            "speed": "Vitesse moyenne réelle sur la section calculée avec (Distance / Temps).\nNe prend pas en compte le dénivelé.",
            "distance": "Distance horizontale entre les deux points de la section.",
            "section": "Points de début et de fin de la section."
        }

        ctk.CTkLabel(
            parent,
            text="Top 20 des meilleures vitesses par section (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 16, "bold")
        ).pack(pady=10)

        columns = ["rank", "bib", "name", "race", "section", "distance", "speed"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "section": "Section",
            "section_width": 300,
            "distance": "Distance",
            "distance_width": 100,
            "speed": "Vitesse",
            "speed_width": 100
        }

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                f"{item['from_point']} → {item['to_point']}",
                f"{item['distance']:.1f} km",
                f"{item['speed']:.1f} km/h"
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(parent, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def convert_time_to_seconds(self, time_str):
        """Convertit un temps au format HH:MM:SS en secondes"""
        try:
            hours, minutes, seconds = map(int, time_str.split(':'))
            return hours * 3600 + minutes * 60 + seconds
        except Exception as e:
            print(f"Erreur lors de la conversion du temps {time_str}: {e}")
            return None

    def update_section_display(self):
        """Mettre à jour l'affichage des performances par section"""
        # Nettoyer l'affichage existant
        for widget in self.section_results_scroll.winfo_children():
            widget.destroy()

        selected_race = self.race_selector.get()
        selected_section = self.section_selector.get()

        if not selected_section or selected_section not in self.sections_info:
            return

        # Utiliser les informations de section stockées
        section_info = self.sections_info[selected_section]

        # Collecter les performances pour la section sélectionnée
        section_performances = []

        for bib in self.bibs:
            if str(bib) in self.scraper.all_data:
                data = self.scraper.all_data[str(bib)]
                if selected_race == "Toutes les courses" or data['infos']['race_name'] == selected_race:
                    checkpoints = data['checkpoints']

                    for i in range(len(checkpoints) - 1):
                        section = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                        if section == selected_section:
                            try:
                                # Calculer le temps de la section en gardant le format HH:MM:SS
                                section_time = self.time_diff(
                                    checkpoints[i + 1]['race_time'],
                                    checkpoints[i]['race_time']
                                )

                                if not section_time:
                                    continue

                                # Pour le calcul des vitesses, on a besoin du temps en heures
                                h, m, s = map(int, section_time.split(':'))
                                hours = h + m / 60 + s / 3600

                                # Calculer la vitesse si le temps est valide
                                if hours > 0:
                                    speed = section_info['distance'] / hours

                                    # Calculer la vitesse effort
                                    effort_speed = (
                                                           section_info['distance'] +
                                                           (section_info['elevation_gain'] / 1000 * 10) +
                                                           (section_info['elevation_loss'] / 1000 * 2)
                                                   ) / hours

                                    # Calculer la progression de classement
                                    rank1 = int(checkpoints[i]['rank']) if checkpoints[i]['rank'] else 0
                                    rank2 = int(checkpoints[i + 1]['rank']) if checkpoints[i + 1]['rank'] else 0
                                    progression = rank1 - rank2 if rank1 and rank2 else 0

                                    # Calculer la tendance (montée/descente/plat)
                                    total_distance_m = section_info['distance'] * 1000
                                    if total_distance_m > 0:
                                        elevation_ratio = (
                                                (section_info['elevation_gain'] - section_info['elevation_loss'])
                                                / total_distance_m
                                        )
                                        if elevation_ratio > 0.05:
                                            tendency = "↗️"
                                        elif elevation_ratio < -0.05:
                                            tendency = "↘️"
                                        else:
                                            tendency = "➡️"
                                    else:
                                        tendency = "➡️"

                                    # Ajouter les performances calculées
                                    section_performances.append({
                                        'bib': bib,
                                        'name': data['infos']['name'],
                                        'race': data['infos']['race_name'],
                                        'time': section_time,  # Format HH:MM:SS
                                        'speed': speed,
                                        'effort_speed': effort_speed,
                                        'progression': progression,
                                        'start_rank': rank1,
                                        'end_rank': rank2,
                                        'tendency': tendency
                                    })

                            except Exception as e:
                                print(f"Erreur lors du calcul des performances: {e}")
                                continue

            # Tri des performances

        def time_to_seconds(time_str):
            """Convertit HH:MM:SS en secondes pour le tri"""
            h, m, s = map(int, time_str.split(':'))
            return h * 3600 + m * 60 + s

            # Pour le tri par temps

        section_performances.sort(key=lambda x: time_to_seconds(x['time']))

        if section_info:
            # Créer la carte d'information de la section
            self.create_section_info_card(self.section_results_scroll, section_info)

            # Créer les tableaux de performance si on a des données
            if section_performances:
                # 1. Classement par temps
                section_performances.sort(key=lambda x: x['time'])
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 temps sur la section",
                    'time'
                )

                # 2. Classement par vitesse
                section_performances.sort(key=lambda x: x['speed'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 vitesses sur la section",
                    'speed'
                )

                # 3. Classement par vitesse effort
                section_performances.sort(key=lambda x: x['effort_speed'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 vitesses effort sur la section",
                    'effort'
                )

                # 4. Classement par progression
                section_performances.sort(key=lambda x: x['progression'], reverse=True)
                self.create_section_performance_table(
                    self.section_results_scroll,
                    section_performances[:20],
                    "Top 20 progressions sur la section",
                    'progression'
                )

    def calculate_effort_speed(self, distance, time_seconds, elevation_gain, elevation_loss):
        """
        Calcule la vitesse effort en prenant en compte le dénivelé

        La formule utilisée est :
        Vitesse effort = (distance + (D+ * facteur_montée) + (D- * facteur_descente)) / temps

        Où:
        - facteur_montée = 10 (100m de D+ équivaut à 1km de distance)
        - facteur_descente = 2 (100m de D- équivaut à 0.2km de distance)
        """
        if time_seconds == 0:
            return 0

        # Conversion des dénivelés en kilomètres équivalents
        elevation_gain_factor = 10  # 1000m D+ = 10km de distance
        elevation_loss_factor = 2  # 1000m D- = 2km de distance

        equivalent_distance = (
                distance +  # Distance réelle
                (elevation_gain / 1000 * elevation_gain_factor) +  # Distance équivalente montée
                (elevation_loss / 1000 * elevation_loss_factor)  # Distance équivalente descente
        )

        hours = time_seconds / 3600
        effort_speed = equivalent_distance / hours

        return effort_speed

    def create_section_performance_table(self, parent, data, title, performance_type):
        """Créer un tableau de performances pour une section spécifique avec tendance"""
        if not data:
            return

        frame = ctk.CTkFrame(parent)
        frame.pack(fill=tk.X, padx=5, pady=10)

        tooltips = {
            "performance": {
                'time': (
                    "Temps réel mis pour parcourir la section.\n"
                    "Calculé comme la différence entre les temps de passage aux deux points.\n"
                    "Inclut les temps d'arrêt éventuels."
                ),
                'speed': (
                    "Vitesse moyenne réelle sur la section.\n"
                    "Calculée avec : Distance / Temps total\n"
                    "Ne prend pas en compte le dénivelé."
                ),
                'effort': (
                    "Vitesse effort qui normalise la performance selon le terrain.\n"
                    "Calculée en prenant en compte :\n"
                    "- La distance réelle\n"
                    "- Le dénivelé positif (facteur 10)\n"
                    "- Le dénivelé négatif (facteur 2)\n"
                    "Permet de comparer les performances sur des terrains différents."
                ),
                'progression': (
                    "Évolution du classement sur la section.\n"
                    "Nombre de places gagnées (valeur positive)\n"
                    "ou perdues (valeur négative)."
                )
            }[performance_type],
            "tendency": "Indication du profil de la section:\n↗️ Montée (>5%)\n➡️ Plat\n↘️ Descente (>5%)"
        }

        ctk.CTkLabel(
            frame,
            text=title + " (Clic droit sur les en-têtes pour plus d'informations)",
            font=("Arial", 14, "bold")
        ).pack(pady=5)

        columns = ["rank", "bib", "name", "race", "performance", "tendency"]
        headers = {
            "rank": "Position",
            "rank_width": 80,
            "bib": "Dossard",
            "bib_width": 80,
            "name": "Nom",
            "name_width": 200,
            "race": "Course",
            "race_width": 150,
            "performance": {
                'time': "Temps",
                'speed': "Vitesse",
                'effort': "Vitesse effort",
                'progression': "Progression"
            }[performance_type],
            "performance_width": 150,
            "tendency": "Tendance",
            "tendency_width": 80
        }

        def format_performance(item):
            if performance_type == 'time':
                return item['time']  # Déjà au format HH:MM:SS
            elif performance_type == 'speed':
                return f"{item['speed']:.1f} km/h"
            elif performance_type == 'effort':
                return f"{item['effort_speed']:.1f} km/h"
            elif performance_type == 'progression':
                return f"+{item['progression']}" if item['progression'] > 0 else str(item['progression'])

        table_data = [
            (
                i + 1,
                item['bib'],
                item['name'],
                item['race'],
                format_performance(item),
                item.get('tendency', '➡️')
            )
            for i, item in enumerate(data)
        ]

        tree = self.create_table(frame, columns, headers, table_data, tooltips=tooltips)
        tree.pack(fill=tk.X, padx=5, pady=5)

    def time_diff(self, time2, time1):
        """
        Calcule la différence entre deux temps au format HH:MM:SS
        Retourne le résultat au format HH:MM:SS
        """
        try:
            # Extraire les heures, minutes, secondes
            h1, m1, s1 = map(int, time1.split(':'))
            h2, m2, s2 = map(int, time2.split(':'))

            # Convertir en secondes pour le calcul
            total_seconds = (h2 * 3600 + m2 * 60 + s2) - (h1 * 3600 + m1 * 60 + s1)

            # Reconvertir en HH:MM:SS
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Erreur lors du calcul de différence de temps: {e}")
            return None

    def create_export_button(self):
        """Créer le bouton d'export avec une image"""
        export_frame = ctk.CTkFrame(self.filter_frame)
        export_frame.pack(side=tk.RIGHT, padx=20)

        try:
            image = Image.open("dl.png")
            image = image.resize((20, 20))
            photo = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter Analyses",
                image=photo,
                compound="left",
                command=self.export_analyses
            )
        except Exception as e:
            print(f"Erreur lors du chargement de l'image: {e}")
            self.export_button = ctk.CTkButton(
                export_frame,
                text="Exporter Analyses",
                command=self.export_analyses
            )

        self.export_button.pack(side=tk.LEFT)

    def export_analyses(self):
        """Exporter toutes les analyses en HTML"""
        try:
            # Créer un dossier pour les exports s'il n'existe pas
            export_dir = "exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            # Timestamp pour le nom des fichiers
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Créer le dossier pour cette analyse
            analysis_dir = os.path.join(export_dir, f"analyses_{timestamp}")
            os.makedirs(analysis_dir)

            # Générer le fichier principal avec les liens vers toutes les analyses
            main_html = self.create_main_analysis_html(timestamp)
            main_file = os.path.join(analysis_dir, "index.html")
            with open(main_file, "w", encoding="utf-8") as f:
                f.write(main_html)

            # Générer les pages d'analyses individuelles
            self.export_progression_analysis(analysis_dir)
            self.export_elevation_analysis(analysis_dir)
            self.export_speed_analysis(analysis_dir)
            self.export_section_analysis(analysis_dir)

            # Ouvrir le fichier principal dans le navigateur
            webbrowser.open(f"file://{os.path.abspath(main_file)}")
            messagebox.showinfo(
                "Export réussi",
                f"Les analyses ont été exportées dans le dossier:\n{analysis_dir}"
            )

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {str(e)}")

    def create_main_analysis_html(self, timestamp):
        """Créer la page principale avec les liens vers toutes les analyses"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Analyses TOP - Grand Raid</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .analysis-card {{
                    transition: transform 0.2s;
                }}
                .analysis-card:hover {{
                    transform: translateY(-5px);
                }}
            </style>
        </head>
        <body class="bg-light">
            <div class="container py-5">
                <h1 class="text-center mb-5">Analyses TOP - Grand Raid</h1>
                <div class="row g-4">
                    <!-- Progression -->
                    <div class="col-md-6 col-lg-3">
                        <div class="card h-100 shadow analysis-card">
                            <div class="card-body">
                                <h5 class="card-title">Progression</h5>
                                <ul class="list-unstyled">
                                    <li><a href="progression_globale.html" class="text-decoration-none">Progression globale</a></li>
                                    <li><a href="progression_sections.html" class="text-decoration-none">Progression entre points</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Dénivelés -->
                    <div class="col-md-6 col-lg-3">
                        <div class="card h-100 shadow analysis-card">
                            <div class="card-body">
                                <h5 class="card-title">Dénivelés</h5>
                                <ul class="list-unstyled">
                                    <li><a href="grimpeurs.html" class="text-decoration-none">Top Grimpeurs</a></li>
                                    <li><a href="descendeurs.html" class="text-decoration-none">Top Descendeurs</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Vitesses -->
                    <div class="col-md-6 col-lg-3">
                        <div class="card h-100 shadow analysis-card">
                            <div class="card-body">
                                <h5 class="card-title">Vitesses</h5>
                                <ul class="list-unstyled">
                                    <li><a href="vitesse_moyenne.html" class="text-decoration-none">Vitesse moyenne</a></li>
                                    <li><a href="vitesse_effort.html" class="text-decoration-none">Vitesse effort</a></li>
                                    <li><a href="vitesse_sections.html" class="text-decoration-none">Vitesse par section</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Sections -->
                    <div class="col-md-6 col-lg-3">
                        <div class="card h-100 shadow analysis-card">
                            <div class="card-body">
                                <h5 class="card-title">Sections</h5>
                                <ul class="list-unstyled">
                                    <li><a href="analyse_sections.html" class="text-decoration-none">Analyse par section</a></li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def get_progression_global_data(self):
        """Récupérer les données du tableau de progression globale"""
        try:
            data = []
            # Trouver le tableau de progression globale dans le frame correspondant
            for widget in self.progress_global_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Position départ
                                values[5],  # Position finale
                                values[6]  # Progression
                            ])
                    break  # Une fois le tableau trouvé et traité, on sort de la boucle

            # Si aucune donnée n'a été trouvée, afficher un message de debug
            if not data:
                print("Aucune donnée trouvée dans le tableau de progression globale")
                # Vérifier quels widgets sont présents
                widgets = [str(type(w)) for w in self.progress_global_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données de progression globale: {str(e)}")
            traceback.print_exc()
            return []

    def get_progression_sections_data(self):
        """Récupérer les données du tableau de progression par sections"""
        try:
            data = []
            # Trouver le tableau dans le frame des sections
            for widget in self.progress_sections_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Section
                                values[5],  # Progression
                                values[6]  # Classements
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau de progression par sections")
                widgets = [str(type(w)) for w in self.progress_sections_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données de progression par sections: {str(e)}")
            traceback.print_exc()
            return []

    def export_progression_analysis(self, export_dir):
        """Exporter les analyses de progression"""
        # Progression globale
        table_data = self.get_progression_global_data()
        html = self.create_analysis_table_html(
            "Progression globale",
            ["Position", "Dossard", "Nom", "Course", "Pos. départ", "Pos. finale", "Progression"],
            table_data
        )
        with open(os.path.join(export_dir, "progression_globale.html"), "w", encoding="utf-8") as f:
            f.write(html)

        # Progression par sections
        table_data = self.get_progression_sections_data()
        html = self.create_analysis_table_html(
            "Progression entre points",
            ["Position", "Dossard", "Nom", "Course", "Section", "Progression", "Classements"],
            table_data
        )
        with open(os.path.join(export_dir, "progression_sections.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def export_elevation_analysis(self, export_dir):
        """Exporter les analyses de dénivelé"""
        # Grimpeurs
        table_data = self.get_climbers_data()
        html = self.create_analysis_table_html(
            "Top Grimpeurs",
            ["Position", "Dossard", "Nom", "Course", "D+ total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
            table_data
        )
        with open(os.path.join(export_dir, "grimpeurs.html"), "w", encoding="utf-8") as f:
            f.write(html)

        # Descendeurs
        table_data = self.get_descenders_data()
        html = self.create_analysis_table_html(
            "Top Descendeurs",
            ["Position", "Dossard", "Nom", "Course", "D- total", "Temps", "Vitesse", "Pente moy.", "Tendance"],
            table_data
        )
        with open(os.path.join(export_dir, "descendeurs.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def export_speed_analysis(self, export_dir):
        """Exporter les analyses de vitesse"""
        # Vitesse moyenne
        table_data = self.get_speed_avg_data()
        html = self.create_analysis_table_html(
            "Vitesse moyenne",
            ["Position", "Dossard", "Nom", "Course", "Vitesse moyenne"],
            table_data
        )
        with open(os.path.join(export_dir, "vitesse_moyenne.html"), "w", encoding="utf-8") as f:
            f.write(html)

        # Vitesse effort
        table_data = self.get_speed_effort_data()
        html = self.create_analysis_table_html(
            "Vitesse effort",
            ["Position", "Dossard", "Nom", "Course", "Vitesse effort"],
            table_data
        )
        with open(os.path.join(export_dir, "vitesse_effort.html"), "w", encoding="utf-8") as f:
            f.write(html)

        # Vitesse par sections
        table_data = self.get_speed_sections_data()
        html = self.create_analysis_table_html(
            "Vitesse par section",
            ["Position", "Dossard", "Nom", "Course", "Section", "Distance", "Vitesse"],
            table_data
        )
        with open(os.path.join(export_dir, "vitesse_sections.html"), "w", encoding="utf-8") as f:
            f.write(html)

    def export_section_analysis(self, export_dir):
        """Exporter l'analyse par section"""
        try:
            # Créer un dossier pour les sections si nécessaire
            sections_dir = os.path.join(export_dir, "sections")
            os.makedirs(sections_dir, exist_ok=True)

            # Générer le HTML pour chaque course
            for course in self.race_values:
                self.race_selector.set(course)
                html = self.create_section_analysis_html()

                # Créer le nom de fichier basé sur la course
                filename = "analyse_sections.html" if course == "Toutes les courses" else f"analyse_sections_{course.lower().replace(' ', '_')}.html"

                with open(os.path.join(export_dir, filename), "w", encoding="utf-8") as f:
                    f.write(html)

        except Exception as e:
            print(f"Erreur lors de l'export de l'analyse des sections: {str(e)}")
            traceback.print_exc()

    def create_analysis_table_html(self, title, headers, data):
        """Créer un tableau HTML pour une analyse"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
            <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
            <style>
                .positive-evolution {{ color: #28a745; }}
                .negative-evolution {{ color: #dc3545; }}
                .neutral-evolution {{ color: #6c757d; }}
                body {{ 
                    background-color: #f8f9fa;
                    padding: 20px;
                }}
                .container-fluid {{
                    background-color: white;
                    border-radius: 8px;
                    padding: 20px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                .table {{ 
                    background-color: white;
                }}
                .table thead th {{
                    background-color: #f8f9fa;
                }}
            </style>
        </head>
        <body>
            <div class="container-fluid">
                <h2 class="mb-4">{title}</h2>
                <a href="index.html" class="btn btn-secondary mb-3">← Retour au menu</a>
                <table id="analysisTable" class="table table-striped table-bordered">
                    <thead>
                        <tr>
                            {"".join(f"<th>{header}</th>" for header in headers)}
                        </tr>
                    </thead>
                    <tbody>
                        {"".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in data)}
                    </tbody>
                </table>
            </div>
            <script>
                $(document).ready(function() {{
                    $('#analysisTable').DataTable({{
                        "pageLength": 50,
                        "language": {{
                            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                        }}
                    }});
                }});
            </script>
        </body>
        </html>
        """
        return html

    def get_climbers_data(self):
        """Récupérer les données du tableau des grimpeurs"""
        try:
            data = []
            # Trouver le tableau dans le frame des grimpeurs
            for widget in self.climbers_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # D+ total
                                values[5],  # Temps
                                values[6],  # Vitesse
                                values[7],  # Pente moyenne
                                values[8]  # Tendance
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau des grimpeurs")
                widgets = [str(type(w)) for w in self.climbers_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données des grimpeurs: {str(e)}")
            traceback.print_exc()
            return []

    def get_descenders_data(self):
        """Récupérer les données du tableau des descendeurs"""
        try:
            data = []
            # Trouver le tableau dans le frame des descendeurs
            for widget in self.descenders_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # D- total
                                values[5],  # Temps
                                values[6],  # Vitesse
                                values[7],  # Pente moyenne
                                values[8]  # Tendance
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau des descendeurs")
                widgets = [str(type(w)) for w in self.descenders_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données des descendeurs: {str(e)}")
            traceback.print_exc()
            return []

    def get_speed_avg_data(self):
        """Récupérer les données du tableau des vitesses moyennes"""
        try:
            data = []
            # Trouver le tableau dans le frame des vitesses moyennes
            for widget in self.speed_avg_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4]  # Vitesse moyenne
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau des vitesses moyennes")
                widgets = [str(type(w)) for w in self.speed_avg_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données des vitesses moyennes: {str(e)}")
            traceback.print_exc()
            return []

    def get_speed_effort_data(self):
        """Récupérer les données du tableau des vitesses effort"""
        try:
            data = []
            # Trouver le tableau dans le frame des vitesses effort
            for widget in self.speed_effort_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4]  # Vitesse effort
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau des vitesses effort")
                widgets = [str(type(w)) for w in self.speed_effort_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données des vitesses effort: {str(e)}")
            traceback.print_exc()
            return []

    def get_speed_sections_data(self):
        """Récupérer les données du tableau des vitesses par section"""
        try:
            data = []
            # Trouver le tableau dans le frame des vitesses par section
            for widget in self.speed_sections_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview):
                    # Pour chaque ligne du tableau
                    for item in widget.get_children():
                        # Récupérer les valeurs de la ligne
                        values = widget.item(item)['values']
                        if values:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Section
                                values[5],  # Distance
                                values[6]  # Vitesse
                            ])
                    break

            if not data:
                print("Aucune donnée trouvée dans le tableau des vitesses par section")
                widgets = [str(type(w)) for w in self.speed_sections_scroll.winfo_children()]
                print(f"Widgets trouvés: {widgets}")

            return data

        except Exception as e:
            print(f"Erreur lors de la récupération des données des vitesses par section: {str(e)}")
            traceback.print_exc()
            return []

    def get_section_time_data(self):
        """Récupérer les données de temps pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Temps
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de temps: {str(e)}")
            return []

    def get_section_speed_data(self):
        """Récupérer les données de vitesse pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Vitesse
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de vitesse: {str(e)}")
            return []

    def get_section_effort_data(self):
        """Récupérer les données de vitesse effort pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Vitesse effort
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de vitesse effort: {str(e)}")
            return []

    def get_section_progression_data(self):
        """Récupérer les données de progression pour la section sélectionnée"""
        try:
            data = []
            for widget in self.section_results_scroll.winfo_children():
                if isinstance(widget, ttk.Treeview) and widget.winfo_ismapped():
                    for item in widget.get_children():
                        values = widget.item(item)['values']
                        if values and len(values) >= 6:
                            data.append([
                                values[0],  # Position
                                values[1],  # Dossard
                                values[2],  # Nom
                                values[3],  # Course
                                values[4],  # Progression
                                values[5]  # Tendance
                            ])
                    break
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données de progression: {str(e)}")
            return []

    def create_section_analysis_html(self):
        """Créer le HTML pour l'analyse de toutes les sections"""
        selected_race = self.race_selector.get()

        # Récupérer la liste des courses disponibles
        courses = ["Toutes les courses"] + sorted(list(set(
            data['infos']['race_name']
            for bib in self.bibs
            if str(bib) in self.scraper.all_data
            for data in [self.scraper.all_data[str(bib)]]
        )))

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Analyse des sections</title>
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css">
            <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/jquery.dataTables.min.js"></script>
            <script src="https://cdn.datatables.net/1.10.24/js/dataTables.bootstrap5.min.js"></script>
            <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.24/css/dataTables.bootstrap5.min.css">
            <style>
                .section-card {
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                    padding: 20px;
                }
                .section-info {
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                }
                .positive-evolution { color: #28a745; }
                .negative-evolution { color: #dc3545; }
                .neutral-evolution { color: #6c757d; }
                body { 
                    background-color: #f8f9fa;
                    padding: 20px;
                }
                .table thead th {
                    background-color: #f8f9fa;
                }
            </style>
        </head>
        <body>
            <div class="container-fluid">
                <h2 class="mb-4">Analyse des sections</h2>
                <a href="index.html" class="btn btn-secondary mb-4">← Retour au menu</a>

                <div class="card mb-4">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col-auto">
                                <label for="courseSelect" class="form-label mb-0"><strong>Sélectionner une course :</strong></label>
                            </div>
                            <div class="col-auto">
                                <select id="courseSelect" class="form-select" style="width: auto;">
        """

        # Ajouter les options de courses
        for course in courses:
            html += f'<option value="{course}"{" selected" if course == selected_race else ""}>{course}</option>'

        html += """
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="sectionsContainer">
                    <div class="accordion" id="sectionsAccordion">
        """

        # Parcourir toutes les sections disponibles
        for i, (section_name, section_info) in enumerate(self.sections_info.items(), 1):
            # Créer un ID unique pour l'accordéon
            section_id = f"section_{i}"

            html += f"""
                <div class="accordion-item mb-3">
                    <h2 class="accordion-header" id="heading_{section_id}">
                        <button class="accordion-button collapsed" type="button" 
                                data-bs-toggle="collapse" data-bs-target="#collapse_{section_id}" 
                                aria-expanded="false" aria-controls="collapse_{section_id}">
                            <strong>{section_name}</strong>
                        </button>
                    </h2>
                    <div id="collapse_{section_id}" class="accordion-collapse collapse"
                         aria-labelledby="heading_{section_id}">
                        <div class="accordion-body">
                            <div class="section-info">
                                <div class="row">
                                    <div class="col-md-4">
                                        <p><strong>Distance :</strong> {section_info['distance']:.1f} km</p>
                                    </div>
                                    <div class="col-md-4">
                                        <p><strong>D+ :</strong> {section_info['elevation_gain']} m</p>
                                    </div>
                                    <div class="col-md-4">
                                        <p><strong>D- :</strong> {section_info['elevation_loss']} m</p>
                                    </div>
                                </div>
                            </div>
            """

            # Récupérer les performances pour cette section
            performances = self.get_section_performances(section_name, selected_race)

            if performances:
                # TOP temps
                if performances['times']:
                    html += self.create_section_table_html(
                        "Top temps",
                        ["Position", "Dossard", "Nom", "Course", "Temps", "Vitesse"],
                        performances['times'],
                        f"time_{section_id}"
                    )

                # TOP progression
                if performances['progressions']:
                    html += self.create_section_table_html(
                        "Top progressions",
                        ["Position", "Dossard", "Nom", "Course", "Progression", "Évolution"],
                        performances['progressions'],
                        f"prog_{section_id}"
                    )

                # TOP vitesse
                if performances['speeds']:
                    html += self.create_section_table_html(
                        "Top vitesses",
                        ["Position", "Dossard", "Nom", "Course", "Vitesse", "Vitesse effort"],
                        performances['speeds'],
                        f"speed_{section_id}"
                    )
            else:
                html += """
                    <div class="alert alert-info">
                        Aucune donnée disponible pour cette section avec les filtres actuels.
                    </div>
                """

            html += """
                        </div>
                    </div>
                </div>
            """

        html += """
                    </div>
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                $(document).ready(function() {
                    // Initialiser tous les datatables
                    $('.datatable').DataTable({
                        "pageLength": 20,
                        "language": {
                            "url": "//cdn.datatables.net/plug-ins/1.10.24/i18n/French.json"
                        }
                    });

                    // Gestionnaire de changement de course
                    $('#courseSelect').change(function() {
                        const selectedCourse = $(this).val();
                        // Stocker la sélection dans localStorage
                        localStorage.setItem('selectedCourse', selectedCourse);
                        // Recharger la page avec la nouvelle sélection
                        const currentUrl = new URL(window.location.href);
                        currentUrl.searchParams.set('course', selectedCourse);
                        window.location.href = currentUrl.toString();
                    });

                    // Restaurer la sélection au chargement
                    const savedCourse = localStorage.getItem('selectedCourse');
                    if (savedCourse) {
                        $('#courseSelect').val(savedCourse);
                    }

                    // Ouvrir automatiquement le premier accordéon si des données sont présentes
                    if($('.accordion-item').length > 0) {
                        $('.accordion-button').first().removeClass('collapsed');
                        $('.accordion-collapse').first().addClass('show');
                    }
                });
            </script>
        </body>
        </html>
        """
        return html
    
    def create_section_table_html(self, title, headers, data, table_id):
        """Créer un tableau HTML pour une catégorie d'analyse de section"""
        html = f"""
            <div class="my-4">
                <h5>{title}</h5>
                <table id="{table_id}" class="table table-striped table-bordered datatable">
                    <thead>
                        <tr>
                            {"".join(f"<th>{header}</th>" for header in headers)}
                        </tr>
                    </thead>
                    <tbody>
                        {"".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in data)}
                    </tbody>
                </table>
            </div>
        """
        return html

    def get_section_performances(self, section_name, selected_race):
        """Récupérer toutes les performances pour une section donnée"""
        times = []
        progressions = []
        speeds = []

        try:
            # Parcourir tous les coureurs
            for bib in self.bibs:
                if str(bib) not in self.scraper.all_data:
                    continue

                runner_data = self.scraper.all_data[str(bib)]

                # Vérifier si le coureur est de la course sélectionnée
                if selected_race != "Toutes les courses" and runner_data['infos']['race_name'] != selected_race:
                    continue

                checkpoints = runner_data['checkpoints']

                # Trouver la section dans les points de passage
                for i in range(len(checkpoints) - 1):
                    current_section = f"{checkpoints[i]['point']} → {checkpoints[i + 1]['point']}"
                    if current_section == section_name:
                        try:
                            # Extraire les performances
                            time1 = datetime.strptime(checkpoints[i]['race_time'], "%H:%M:%S")
                            time2 = datetime.strptime(checkpoints[i + 1]['race_time'], "%H:%M:%S")
                            section_time = time2 - time1

                            # Calcul de la vitesse
                            hours = section_time.total_seconds() / 3600
                            distance = checkpoints[i + 1]['kilometer'] - checkpoints[i]['kilometer']
                            speed = distance / hours if hours > 0 else 0

                            # Calcul de la vitesse effort
                            d_plus = checkpoints[i]['elevation_gain'] or 0
                            d_minus = checkpoints[i]['elevation_loss'] or 0
                            effort_distance = distance + (d_plus / 1000 * 10) + (d_minus / 1000 * 2)
                            effort_speed = effort_distance / hours if hours > 0 else 0

                            # Progression
                            rank1 = int(checkpoints[i]['rank']) if checkpoints[i]['rank'] else 0
                            rank2 = int(checkpoints[i + 1]['rank']) if checkpoints[i + 1]['rank'] else 0
                            progression = rank1 - rank2 if rank1 and rank2 else 0

                            # Ajouter aux listes
                            times.append([
                                len(times) + 1,
                                bib,
                                runner_data['infos']['name'],
                                runner_data['infos']['race_name'],
                                str(section_time).split('.')[0],
                                f"{speed:.1f} km/h"
                            ])

                            progressions.append([
                                len(progressions) + 1,
                                bib,
                                runner_data['infos']['name'],
                                runner_data['infos']['race_name'],
                                progression,
                                f"{rank1} → {rank2}"
                            ])

                            speeds.append([
                                len(speeds) + 1,
                                bib,
                                runner_data['infos']['name'],
                                runner_data['infos']['race_name'],
                                f"{speed:.1f} km/h",
                                f"{effort_speed:.1f} km/h"
                            ])

                        except Exception as e:
                            print(f"Erreur lors du calcul des performances pour le dossard {bib}: {str(e)}")
                        break

            # Trier les listes
            times.sort(key=lambda x: datetime.strptime(x[4], "%H:%M:%S"))
            progressions.sort(key=lambda x: x[4], reverse=True)
            speeds.sort(key=lambda x: float(x[4].split()[0]), reverse=True)

            # Limiter à TOP 20
            times = times[:20]
            progressions = progressions[:20]
            speeds = speeds[:20]

            # Mettre à jour les positions après le tri
            for i, perf in enumerate(times, 1):
                perf[0] = i
            for i, perf in enumerate(progressions, 1):
                perf[0] = i
            for i, perf in enumerate(speeds, 1):
                perf[0] = i

            return {
                'times': times,
                'progressions': progressions,
                'speeds': speeds
            }

        except Exception as e:
            print(f"Erreur lors de la récupération des performances de la section {section_name}: {str(e)}")
            return {'times': [], 'progressions': [], 'speeds': []}




if __name__ == "__main__":
    app = RaceTrackerApp()
    app.run()